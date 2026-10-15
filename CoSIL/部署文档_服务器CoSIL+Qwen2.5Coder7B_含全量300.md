# 部署文档：组服务器复现 CoSIL + Qwen2.5-Coder-7B（含全量 300 题，交由执行模型）

> 目标：在实验室 Linux GPU 服务器上用 vLLM 部署 Qwen2.5-Coder-7B-Instruct，运行**原版 CoSIL**（ZJU-CTAG 版，零源码修改），先跑金丝雀，再分批跑完 SWE-bench Lite 全量 300 题。
> 前提：已获得服务器 SSH 账号；服务器为多人共用，全程遵守文末使用守则。
> 与本机版部署文档的差异：无 WSL2 段（原生 Linux）；新增环境侦察、共享卡选择、tmux 强制、全量分批跑法。

---

## 阶段 0：环境侦察（先做，结果记入交付物）

```bash
nvidia-smi                                    # GPU 型号/数量/驱动版本/当前占用
nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv   # 各卡占用一览
df -h ~                                       # home 磁盘配额（本次共需约 50GB）
conda --version 2>/dev/null || echo "无conda"  # 有无公共 conda
python3 --version
ss -tlnp 2>/dev/null | grep 7333 || echo "端口7333空闲"
curl -sI https://mirrors.tuna.tsinghua.edu.cn -m 5 | head -1   # 网络可达性（清华镜像）
curl -sI https://modelscope.cn -m 5 | head -1                  # ModelScope 可达性
git --version
```

分支决策：
- 驱动 ≥ 525（CUDA 12.x）→ 直接 `pip install -U vllm`；驱动太老 → **不要自己动驱动**，记录版本反馈给用户（需找管理员）。
- GPU 为 A100/A800/H100/H800/4090/3090 任一 → vLLM 均支持，无需特殊处理。
- 无 conda → 装 Miniconda 到 home（命令见下）。有公共 conda → 仍自建环境，不污染公共环境。

## 阶段 1：Miniconda 与环境（如已有 conda 跳过安装）

```bash
wget https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh    # 默认安装到 ~/miniconda3，最后 yes 让 conda init
source ~/.bashrc
conda create -n cosil python=3.11 -y && conda activate cosil
```

## 阶段 2：vLLM 与模型下载（约 15GB，占 home 配额）

```bash
pip install -U vllm -i https://pypi.tuna.tsinghua.edu.cn/simple
python -c "import vllm; print(vllm.__version__)"          # 检查点①
pip install modelscope -i https://pypi.tuna.tsinghua.edu.cn/simple
python -c "from modelscope import snapshot_download; snapshot_download('Qwen/Qwen2.5-Coder-7B-Instruct', local_dir='~/models/qwen25coder7b')"
```

> 模型名以**论文**为准（Qwen2.5-**Coder**-7B-Instruct），不是 CoSIL 仓库脚本里的通用版 qwen2.5-7b-instruct。

## 阶段 3：起模型服务（tmux 内，选空卡）

```bash
# 1. 选卡：看 nvidia-smi，取显存占用接近 0 MiB 的卡号（假设是 3）
# 2. tmux 里启动（长任务必须 tmux，SSH 断开不杀进程）
tmux new -s llm
conda activate cosil
CUDA_VISIBLE_DEVICES=3 vllm serve ~/models/qwen25coder7b \
  --served-model-name llama3 \
  --port 7333 \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.92
# 挂后台：Ctrl+B 再按 D     （回来：tmux attach -t llm）
```

> "llama3" 是 CoSIL 原版代码里本地 vLLM 的约定路由键（模型名含 llama3 → 请求发 127.0.0.1:7333），借此**零源码修改**接上 Qwen。
> 端口 7333 被占的话：换 7334 并把 CoSIL 的 `afl/util/api_requests.py` 里 `7333` 改为 `7334`（这是唯一允许的源码改动，需记录）。

检查点②（另开终端，无需 tmux）：

```bash
curl http://127.0.0.1:7333/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"llama3","messages":[{"role":"user","content":"回复：通了"}],"max_tokens":10}'
```

## 阶段 4：CoSIL 原版与数据

```bash
mkdir -p ~/cosil_repro && cd ~/cosil_repro
git clone https://github.com/ZJU-CTAG/CoSIL.git    # 论文对应实现（勿用任何本地插桩副本）
cd CoSIL
pip install -r requirments.txt -i https://pypi.tuna.tsinghua.edu.cn/simple   # 文件名就是这个拼写
pip install datasets tiktoken
```

仓库结构缓存（二选一，A 优先）：
- A：浏览器/命令行从 `https://github.com/OpenAutoCoder/Agentless/releases/tag/v1.5.0` 下 structure files 压缩包，解压到 `~/cosil_repro/structures/`；
- B：`export HF_ENDPOINT=https://hf-mirror.com && python get_lite_structure.py`（自行克隆 12 仓库，1-2 小时，需再 ~10GB 磁盘）。

环境变量（追加进 `~/.bashrc` 后 `source`）：

```bash
export PYTHONPATH=$PYTHONPATH:~/cosil_repro/CoSIL
export PROJECT_FILE_LOC=~/cosil_repro/structures
export HF_ENDPOINT=https://hf-mirror.com
```

## 阶段 5：金丝雀（单题）

```bash
cd ~/cosil_repro/CoSIL && conda activate cosil
ln -s ~/cosil_repro/structures repo_structures   # FL_tools 硬编码相对路径
python afl/fl/AFL_localize_file.py --file_level \
  --output_folder results/canary --output_file loc_out.jsonl \
  --num_threads 1 --model llama3 --backend openai --skip_existing \
  --target_id astropy__astropy-12907
python afl/fl/AFL_localize_func.py \
  --output_folder results/canary --output_file loc_func.jsonl \
  --loc_file results/canary/loc_out.jsonl \
  --num_threads 1 --model llama3 --backend openai --skip_existing \
  --temperature 0.0 --target_id astropy__astropy-12907
```

检查点③：两个 jsonl 各含一行该 instance 的 JSON。
已知坑：少 `--file_level` → 断言错；输出已存在没 `--skip_existing` → 断言错；温度一律 **0.0**（论文 E 节 greedy，仓库脚本 0.85 与论文矛盾，以论文为准）。

## 阶段 6：全量 300 分批跑法（核心增量）

原则：**每批一个 tmux 会话；批内断点续跑；每批结束收档**。批大小建议 75 题（约一晚）。

```bash
tmux new -s batch1
conda activate cosil && cd ~/cosil_repro/CoSIL
# 文件级全量（--skip_existing 天然断点续跑：已写入输出文件的题自动跳过）
nohup python afl/fl/AFL_localize_file.py --file_level \
  --output_folder results/full --output_file loc_out_full.jsonl \
  --num_threads 8 --model llama3 --backend openai --skip_existing \
  > ~/cosil_repro/logs_file_batch1.log 2>&1 &
# 进度查看：
wc -l results/full/loc_out_full.jsonl          # 到 300 即完成
# 函数级全量（文件级 300 行齐了再跑）
nohup python afl/fl/AFL_localize_func.py \
  --output_folder results/full --output_file loc_func_full.jsonl \
  --loc_file results/full/loc_out_full.jsonl \
  --num_threads 8 --model llama3 --backend openai --skip_existing --temperature 0.0 \
  > ~/cosil_repro/logs_func_batch1.log 2>&1 &
```

要点：
- `--num_threads 8` 起步；若 vLLM 端出现超时/排队报错降到 4；单卡 7B 伺候 8 并发没压力；
- 中断/断网/断电都不怕：重跑同一条命令，已完成的题被 `--skip_existing` 跳过；
- 每批跑完收档：`cp results/full/*.jsonl ~/cosil_repro/archive/$(date +%m%d)_文件级/`；
- 全程时长预估：文件级 300 题 ≈ 5-10 小时；函数级 ≈ 10-20 小时。**通宵批次开跑前，让用户在组群报备**（守则见文末）。

## 阶段 7：交付物清单

1. `loc_out_full.jsonl` 与 `loc_func_full.jsonl`（300 行各）——**原样不动**传回；
2. 阶段 0 侦察记录（GPU 型号/驱动/磁盘/网络）；
3. 三个检查点的输出文本；
4. vLLM 版本、所用卡号、有无源码改动（默认无；端口被迫改动须注明）；
5. 跑批日志 `logs_*_batch1.log` 原文。
传回方式：用户用 WinSCP 拖回，或 `scp` 至 Windows 侧。

## 附：服务器使用守则（执行模型也须遵守）

1. 用卡前 `nvidia-smi`，只用空闲卡，通过 `CUDA_VISIBLE_DEVICES` 指定，**不碰他人进程的卡**；
2. 一切超过 5 分钟的任务进 tmux；会话命名可识别（llm/batch1）；
3. 通宵/长批次前由用户在组群报备：占哪张卡、大约多久；
4. 不动 `/home/他人` 与公共目录；模型装自己 home；
5. 实验全部结束后：停 vLLM（tmux 会话 kill）+ 释放显存 + 告知用户可 `rm -rf ~/models` 回收 15GB（留待用户决定）。
