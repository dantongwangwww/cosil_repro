import re
import os
import json
import argparse
from utils.constants import NON_VAILD_ISSUES
from utils.string_processing import load_jsonl
from rdfs.dependency_graph.dependency_graph import DependencyGraph
from utils.construct_graph import construct_rdfs_skeleton, clone_repo, checkout_commit
from utils.convert_results import convert_results
from search_agent import SearchAgent
from causal_agent import CausalAgent 

def parse_arguments():
    parser = argparse.ArgumentParser(description="GraphLocator for issue localization and causal graph generation.")
    parser.add_argument("--dataset_name", type=str, default="swe_bench_lite",
                        help="Name of the dataset to process.")
    parser.add_argument("--dataset_language", type=str, choices=["python", "java"], default="python",
                        help="Programming language of the dataset.")
    parser.add_argument("--model_name", type=str, default="gpt-4o-2024-11-20",
                        help="Name of the model to use for generating causal graphs, can be gpt-4o-2024-11-20 or claude-3-5-sonnet-20241022.")
    parser.add_argument("--repo_playground", type=str, default="AbsolutePath/GraphLocator/repo_playground",
                        help="Path to the repository playground.")
    parser.add_argument("--repo_skeleton_path", type=str, default="./repo_skeleton",
                        help="Path to the repository skeleton.")
    parser.add_argument("--results_dir", type=str, default="./results/swe_bench_lite/gpt4o",
                        help="Directory to save the results.")
    parser.add_argument("--search_topk", type=int, default=5,
                        help="Top K search results to consider.")
    parser.add_argument("--skip_exist", action='store_true',
                        help="Whether to skip already processed issues.")
    parser.add_argument("--max_search_turn", type=int, default=5,
                        help="Maximum number of search turns for the SearchAgent.")
    parser.add_argument("--max_causal_turn", type=int, default=20,
                        help="Number of causal graph generation turns for the CausalAgent.")
                        
    return parser.parse_args()

def main(args):

    # Read the issue dataset and load the already processed issues if skip_exist is set
    ds = load_jsonl(f"./datasets/{args.dataset_name}.jsonl")
    loc_res = dict()

    if not os.path.exists(args.results_dir):
        os.makedirs(args.results_dir)
    if args.skip_exist:
        if not os.path.exists(f"{args.results_dir}/causal_graph/"):
            already_processed = []
        else:
            already_processed = [f.split('.')[0] for f in os.listdir(f"{args.results_dir}/causal_graph/") if f.endswith('.json')]

    # Process each issue in the dataset
    for issue in ds:

        issue_id = issue['instance_id']
        if issue_id in NON_VAILD_ISSUES or (args.skip_exist and issue_id in already_processed):
            continue
        
        # Step 0: Prepare the repository graph and checkout the correct commit
        if not os.path.exists(f"./{args.repo_skeleton_path}"):
            os.makedirs(f"./{args.repo_skeleton_path}")
        if not os.path.exists(f"./{args.repo_skeleton_path}/{issue_id}.json"):
            print(f"Graph cache for issue {issue_id} not found, construct...")
            construct_rdfs_skeleton(issue, args.repo_skeleton_path, args.repo_playground, args.dataset_language)
        with open(f"{args.repo_skeleton_path}/{issue_id}.json", "r") as f:
            graph_data = f.read()
        graph = DependencyGraph.from_json(graph_data)

        repo_name = issue['repo'].split('/')[-1]
        commit_id = issue["base_commit"]
        checkout_commit(f"{args.repo_playground}/{repo_name}", commit_id)

        # Step 1: symptom vertices localization
        search_agent = SearchAgent(repo_graph=graph, model_name=args.model_name, max_search_turn=args.max_search_turn, top_k=args.search_topk)
        seed_locations = search_agent.get_seed_location(issue['problem_statement'])

        # Step 2: dynamic CIG discovering
        causal_agent = CausalAgent(model_name=args.model_name, repo_graph=search_agent.repo_graph, max_turn=args.max_causal_turn)
        cig = causal_agent.generate_causal_graph(issue['problem_statement'], seed_locations)

        # Convert CIG to 3-level of granularity results
        loc_res[issue_id] = convert_results(cig, graph)
        with open(f"{args.results_dir}/loc_results.json", "w") as f:
            json.dump(loc_res, f, indent=2)


if __name__ == "__main__":

    args = parse_arguments()
    main(args)