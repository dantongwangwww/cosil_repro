import hashlib
import importlib.util
import json
from pathlib import Path
import random
import tempfile
import unittest

from specprune.codec import Codec, example_loss
from specprune.input_format import body, native, fit_input, assert_v6_row, INPUT_VERSION
from specprune.model_ops import collate_features, reranker_loss, RERANKER_PREFIX, RERANKER_SUFFIX, TASK
from specprune.training import load_data, ordered_groups, normalized_group_weights, validate_recipe


def example(iid='issue1', fid='a.py::f', split='train', label=True):
    text = body('Something broke', 'def f():\n    return 1', 'callers: none\ncallees: none')
    return {'instance_id': iid, 'function_id': fid, 'split': split, 'label': label,
            'sample_weight': 1.0, 'input_version': INPUT_VERSION,
            'issue': 'Something broke', 'function': 'def f():\n    return 1',
            'neighbors': 'callers: none\ncallees: none', 'model_input': text,
            'input_sha256': hashlib.sha256(text.encode()).hexdigest()}


class Tokenizer:
    pad_token_id = 0
    pad_token = '<pad>'
    eos_token = '<eos>'
    def encode(self, text, add_special_tokens=False):
        if text == 'no':
            return [1]
        if text == 'yes':
            return [2]
        return [3] * len(text)


class TrainingContractTest(unittest.TestCase):
    def test_unsupported_recipe_switches_fail_closed(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'configs/training.json').read_text())
        validate_recipe(config)
        for key, value in [('dtype', 'float32'), ('max_tokens', 4096), ('learning_rate_schedule', 'cosine'),
                           ('gradient_checkpointing', False), ('warmup_backward_without_update', False)]:
            with self.assertRaisesRegex(ValueError, 'Unsupported recipe'):
                validate_recipe({**config, key: value})

    def test_native_text_and_no_retruncation(self):
        tok = Tokenizer()
        row = example()
        row['issue'] = 'x' * 2300
        row['model_input'] = body(row['issue'], row['function'], row['neighbors'])
        rendered = native(tok, 'reranker', row['model_input'])
        self.assertEqual(rendered, RERANKER_PREFIX + f'<Instruct>: {TASK}\n<Query>: Judge the issue/function pair in the following record.\n<Document>: {row["model_input"]}' + RERANKER_SUFFIX)
        encoded = Codec(tok, 'reranker').encode(row)
        self.assertEqual(len(encoded['input_ids']), len(rendered))
        self.assertIn('x' * 2300, rendered)
        self.assertEqual(encoded['candidates'], [[1], [2]])

    def test_overlong_and_modified_input_are_rejected(self):
        row = example()
        row['issue'] = 'x' * 9000
        row['model_input'] = body(row['issue'], row['function'], row['neighbors'])
        with self.assertRaisesRegex(ValueError, 'no recropping'):
            Codec(Tokenizer(), 'reranker').encode(row)
        row = example()
        row['function'] += '\n# changed'
        with self.assertRaisesRegex(ValueError, 'drift'):
            assert_v6_row(row)

    def test_fit_preserves_original_prefixes_and_drops_neighbors_first(self):
        fitted = fit_input({'test': (Tokenizer(), 'reranker')}, 'i' * 3000, 'f' * 2500,
                           'header\n' + '\n'.join('n' * 100 for _ in range(30)))
        self.assertEqual(fitted['issue'], 'i' * 3000)
        self.assertEqual(fitted['function'], 'f' * 2500)
        self.assertLess(len(fitted['neighbors']), 3036)
        self.assertTrue(fitted['token_budget_trimmed'])

    def test_group_shuffle_and_normalization_match_original(self):
        ordered = list(range(19))
        random.Random(2).shuffle(ordered)
        groups = ordered_groups(19, 2)
        self.assertEqual(groups, [ordered[:8], ordered[8:16], ordered[16:]])
        rows = [{'sample_weight': 0.5}, {'sample_weight': 2.0}, {'sample_weight': 1.0}]
        self.assertEqual(normalized_group_weights(rows, [0, 1]), [0.2, 0.8])

    def test_dataset_requires_issue_split_isolation_and_exact_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / 'a.jsonl', Path(directory) / 'b.jsonl'
            train, val = example(), example('issue2', split='val')
            a.write_text(json.dumps(train) + '\n'); b.write_text(json.dumps(val) + '\n')
            self.assertEqual(len(load_data(a, b)['train']), 1)
            val['instance_id'] = 'issue1'; val['function_id'] = 'a.py::g'
            b.write_text(json.dumps(val) + '\n')
            with self.assertRaisesRegex(ValueError, 'leakage'):
                load_data(a, b)
            val['instance_id'] = 'issue2'; val['input_sha256'] = 'f' * 64
            b.write_text(json.dumps(val) + '\n')
            with self.assertRaisesRegex(ValueError, 'SHA'):
                load_data(a, b)
            val['split'] = 'test'; b.write_text(json.dumps(val) + '\n')
            with self.assertRaisesRegex(ValueError, 'train/val'):
                load_data(a, b)


@unittest.skipUnless(importlib.util.find_spec('torch'), 'Optional training dependency torch not installed')
class BinaryLossTest(unittest.TestCase):
    def test_left_padding_binary_ce_and_weighted_gradients(self):
        import torch
        import torch.nn.functional as F
        from types import SimpleNamespace
        class Toy(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.logits = torch.nn.Parameter(torch.tensor([0.3, 1.2, -0.7, 5.5]))
            def forward(self, input_ids, attention_mask, use_cache, logits_to_keep):
                self.last = (attention_mask.clone(), use_cache, logits_to_keep)
                return SimpleNamespace(logits=self.logits.expand(len(input_ids), 1, 4))
        model = Toy()
        features = [{'input_ids': [3], 'label': 0}, {'input_ids': [3, 2], 'label': 1}]
        batch = collate_features(features, 0)
        self.assertEqual(batch['input_ids'].tolist(), [[0, 3], [3, 2]])
        self.assertEqual(batch['attention_mask'].tolist(), [[0, 1], [1, 1]])
        actual = reranker_loss(model, batch, no_id=1, yes_id=2)
        reference = F.cross_entropy(model.logits[[1, 2]].expand(2, 2), torch.tensor([0, 1]))
        self.assertTrue(torch.equal(actual, reference))
        self.assertEqual(model.last[1:], (False, 1))
        codec = SimpleNamespace(kind='reranker', no_id=1, yes_id=2)
        with self.assertRaisesRegex(ValueError, 'microbatch one'):
            example_loss(model, batch, codec)
        model.zero_grad()
        for feature, weight in zip(features, [0.5, 2.0]):
            loss = example_loss(model, collate_features([feature], 0), codec)
            (loss * weight / 2.5).backward()
        observed = model.logits.grad.clone()
        model.zero_grad()
        losses = F.cross_entropy(model.logits[[1, 2]].expand(2, 2), torch.tensor([0, 1]), reduction='none')
        ((losses * torch.tensor([0.5, 2.0])).sum() / 2.5).backward()
        torch.testing.assert_close(observed, model.logits.grad)
        self.assertEqual(observed[[0, 3]].tolist(), [0.0, 0.0])


if __name__ == '__main__':
    unittest.main()
