import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from specprune.scoring import input_for_scoring, load_deployment, validate_adapter
from specprune.input_format import body, INPUT_VERSION
from specprune.model_ops import verify_base_model
from specprune.metrics import calibrated_probability, hybrid_route, fit_temperature, apply_temperature, roc_auc


class ScoringContractTest(unittest.TestCase):
    def test_labels_provenance_never_enter_scoring_input(self):
        text = body('issue', 'def f(): pass', 'none')
        row = {'issue': 'issue', 'function': 'def f(): pass', 'neighbors': 'none',
               'model_input': text, 'input_version': INPUT_VERSION, 'label': True,
               'gold': 'secret', 'provenance': 'secret', 'input_sha256': hashlib.sha256(text.encode()).hexdigest()}
        clean = input_for_scoring(row)
        self.assertNotIn('gold', clean)
        self.assertNotIn('provenance', clean)
        self.assertFalse(clean['label'])
        self.assertEqual(clean['model_input'], text)
        row['input_sha256'] = 'x'
        with self.assertRaisesRegex(ValueError, 'SHA'):
            input_for_scoring(row)

    def test_temperature_route_boundaries_and_nonfinite(self):
        self.assertEqual(calibrated_probability(0.5, 2.9846201034621833, logit_difference=0.0), 0.5)
        self.assertEqual(hybrid_route(0.12947567721292427, low=0.12947567721292427), 'reject')
        self.assertEqual(hybrid_route(0.9, low=0.12947567721292427), 'retain')
        self.assertEqual(hybrid_route(0.5, low=0.12947567721292427), 'qwen')
        for value in [float('nan'), float('inf'), -0.1, 1.1]:
            with self.assertRaises(ValueError):
                hybrid_route(value)
        with self.assertRaises(ValueError):
            calibrated_probability(0.5, 1, logit_difference=9)

    def test_adapter_exact_digest_and_architecture(self):
        config = load_deployment()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            data = b'opaque fake adapter used only for SHA validation'
            (path / 'adapter_model.safetensors').write_bytes(data)
            (path / 'adapter_config.json').write_text(json.dumps({'peft_type': 'LORA', 'r': 16, 'lora_alpha': 32}))
            config['adapter_sha256'] = hashlib.sha256(data).hexdigest()
            config['adapter_config_sha256'] = hashlib.sha256((path / 'adapter_config.json').read_bytes()).hexdigest()
            self.assertEqual(validate_adapter(path, config)['rank'], 16)
            original_config = (path / 'adapter_config.json').read_text()
            (path / 'adapter_config.json').write_text(original_config + ' ')
            with self.assertRaisesRegex(ValueError, 'config SHA'):
                validate_adapter(path, config)
            (path / 'adapter_config.json').write_text(original_config)
            (path / 'adapter_model.safetensors').write_bytes(data + b'drift')
            with self.assertRaisesRegex(ValueError, 'SHA'):
                validate_adapter(path, config)

    def test_base_weights_cannot_be_shadowed(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'model-00001-of-00001.safetensors').write_bytes(b'verified shard')
            expected = {'model-00001-of-00001.safetensors': hashlib.sha256(b'verified shard').hexdigest()}
            self.assertEqual(verify_base_model(folder, expected)['verified_files'], 1)
            (folder / 'model.safetensors').write_bytes(b'unverified preferred file')
            with self.assertRaisesRegex(ValueError, 'alternative'):
                verify_base_model(folder, expected)

    def test_temperature_is_val_only_and_auc_ties(self):
        rows = [{'instance_id': f'i{x}', 'function_id': 'f.py::g', 'label': label, 'p_yes': p,
                 'split': 'val', 'label_sources': ['A'] if label else ['D']}
                for x, (label, p) in enumerate([(True, .9), (False, .9), (True, .1), (False, .1)])]
        self.assertEqual(roc_auc(rows), 0.5)
        fit = fit_temperature(rows)
        self.assertGreaterEqual(fit['nll_before'], fit['nll_after'])
        adjusted = apply_temperature(rows, fit['temperature'])
        with self.assertRaises(ValueError):
            apply_temperature(adjusted, fit['temperature'])
        rows[0]['split'] = 'train'
        with self.assertRaisesRegex(ValueError, 'val'):
            fit_temperature(rows)


if __name__ == '__main__':
    unittest.main()
