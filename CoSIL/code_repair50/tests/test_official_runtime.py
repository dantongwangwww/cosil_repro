"""Synthetic safety checks; no daemon, network, registry, or third-party tests."""
import struct
import unittest
from unittest.mock import patch

from code_repair50 import official_runtime as R


class CapacityTests(unittest.TestCase):
    def test_actual_first_task_lower_bound_blocks_without_cache_credit(self):
        gate = R.capacity_gate(5218357248, 1852798126, 4101332992)
        self.assertEqual(gate["status"], "BLOCKED_DISK_CAPACITY")
        self.assertEqual(gate["projected_uncached_minimum_with_reserve_bytes"], 8101614766)
        self.assertFalse(gate["allow_pull"])
        self.assertFalse(gate["allow_container_tests"])
        self.assertFalse(gate["allow_model_generation"])

    def test_unknown_storage_or_uncompressed_size_is_not_zero(self):
        for values in ((None, 10, 20), (100, None, 20), (100, 10, None)):
            with self.subTest(values=values):
                self.assertEqual(R.capacity_gate(*values)["status"], "BLOCKED_STORAGE_ESTIMATE_UNKNOWN")

    def test_lower_bound_fitting_is_not_a_safe_upper_bound(self):
        gate = R.capacity_gate(10000000000, 10, 20)
        self.assertEqual(gate["status"], "LOWER_BOUND_FITS_UPPER_BOUND_STILL_UNVERIFIED")
        self.assertFalse(gate["allow_pull"])

    def test_valid_partial_response_proves_only_gzip_modulo_lower_bound(self):
        value = R.valid_footer(206, "bytes 96-99/100", struct.pack("<I", 4101331968), 100)
        self.assertEqual(value, 4101331968)

    def test_full_body_or_wrong_range_is_not_a_gzip_footer(self):
        for status, header, body in ((200, None, b"1234"), (206, "bytes 0-3/100", b"1234"),
                                      (206, "bytes 96-99/100", b"12345")):
            with self.subTest(status=status, header=header):
                self.assertIsNone(R.valid_footer(status, header, body, 100))

    def test_mutating_daemon_commands_cannot_be_called(self):
        for command in (("docker", "pull", "swerebench/x:latest"),
                        ("docker", "image", "prune"), ("docker", "run", "x")):
            with self.subTest(command=command), patch.object(R.subprocess, "run") as run:
                with self.assertRaises(ValueError):
                    R.readonly_command(command)
                run.assert_not_called()

    def test_nonofficial_registry_ref_rejected_before_network(self):
        with patch.object(R, "_get") as network:
            with self.assertRaises(ValueError):
                R.registry_manifest("unrelated.example/task:latest")
            network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
