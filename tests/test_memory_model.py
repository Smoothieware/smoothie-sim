"""Unit tests of the LPC1768 heap replay (checkers/memory_check.py) and the layout parser. Run: python3 -I tests/test_memory_model.py
Test cases follow the ones of the Carvera Firmware Simulator's tests/lpc_memory_accounting_test.cpp (Copyright (c) 2026 Konstantin Tcepliaev, GPLv3+).
"""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "checkers"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import memory_check as mc, lpc_dwarf, lpc_memory_layout as lay

LAYOUT = {"main_sram": {"ram_start": 0x100000C8, "ram_end": 0x10008000, "heap_start": 0x10001000, "stack_limit": 0x10001400, "stack_top": 0x10008000},
          "ahb0": {"pool_start": 0x2007C100, "pool_end": 0x2007C200}}   # 1 KiB heap room, 256 B AHB pool
MAP = """Memory Configuration
RAM              0x00000000100000c8 0x0000000000007f38
USB_RAM          0x000000002007c000 0x0000000000004000
ETH_RAM          0x0000000020080000 0x0000000000004000
                0x0000000010001000                __end__ = .
                0x0000000010001400                __StackLimit = (__StackTop - SIZEOF (.stack_dummy))
                0x0000000010008000                __StackTop = (ORIGIN (RAM) + LENGTH (RAM))
                0x000000002007c100                PROVIDE (__AHB0_dyn_start = .)
                0x0000000020080000                PROVIDE (__AHB0_end = (ORIGIN (USB_RAM) + LENGTH (USB_RAM)))
"""
DWARF = """ <1><2d>: Abbrev Number: 2 (DW_TAG_class_type)
    <2e>   DW_AT_name        : (indirect string, offset: 0x1): Planner
    <32>   DW_AT_byte_size   : 168
 <1><40>: Abbrev Number: 3 (DW_TAG_member)
    <41>   DW_AT_name        : x
    <42>   DW_AT_byte_size   : 4
 <1><50>: Abbrev Number: 4 (DW_TAG_structure_type)
    <51>   DW_AT_name        : Block
    <52>   DW_AT_byte_size   : 0x70
"""


class Replay(unittest.TestCase):
    def test_header_and_alignment(self):
        r = mc.replay([("a", 1, 1, 0)], LAYOUT)["main_sram"]
        self.assertEqual(r["peak_live_bytes"], 16)   # 1 B + 8 B header = 9 -> minimum block 16

    def test_peak_free_and_reuse(self):
        ev = [("a", 1, 100, 0), ("a", 2, 100, 0), ("f", 1), ("a", 3, 50, 0), ("f", 2), ("f", 3)]
        r = mc.replay(ev, LAYOUT)["main_sram"]
        self.assertEqual((r["peak_live_bytes"], r["live_bytes_at_end"], r["failed_allocations"]), (224, 0, 0))   # two 100 B requests are 112 B blocks
        self.assertEqual(r["margin_to_stack_bytes"], 0x400 - 224)   # the break reached heap_start + 224

    def test_failure_and_margin(self):
        r = mc.replay([("a", 1, 1000, 0), ("a", 2, 100, 0)], LAYOUT)["main_sram"]
        self.assertEqual((r["failed_allocations"], r["failed_bytes"]), (1, 100))

    def test_fragmentation(self):
        ev = [("a", i, 40, 0) for i in range(1, 7)] + [("f", 2), ("f", 4)]
        r = mc.replay(ev, LAYOUT)["main_sram"]
        self.assertEqual(r["largest_free_block"], 0x400 - 6 * 48)   # the gap above the break is the largest block
        self.assertEqual(r["fragmented_free_bytes"], 96)

    def test_trim_at_top(self):
        r = mc.replay([("a", 1, 100, 0), ("f", 1)], LAYOUT)["main_sram"]
        self.assertEqual(r["largest_free_block"], 0x400)

    def test_ahb_pool_semantics(self):
        ev = [("a", 1, 100, 1), ("a", 2, 100, 1), ("a", 3, 100, 1)]   # 104 B each in a 256 B pool: the third fails
        h = mc.replay(ev, LAYOUT)["ahb0"]
        self.assertEqual((h["peak_live_bytes"], h["failed_allocations"], h["pool_bytes"]), (208, 1, 256))
        h = mc.replay(ev[:2] + [("f", 1), ("f", 2), ("a", 4, 240, 1)], LAYOUT)["ahb0"]   # coalescing frees room for one big block
        self.assertEqual(h["failed_allocations"], 0)

    def test_size_mapping(self):
        self.assertEqual(mc.arm_size_for(200, ["Planner::Planner()"], {"Planner": 200}, {"Planner": 168}), (168, True))
        self.assertEqual(mc.arm_size_for(64, ["Planner::Planner()"], {"Planner": 200}, {"Planner": 168}), (64, False))


class Layout(unittest.TestCase):
    def test_parse(self):
        lo = lay.build_layout(MAP, {"Planner": 168})
        self.assertEqual((lo["main_sram"]["heap_start"], lo["main_sram"]["stack_limit"], lo["ahb0"]["pool_start"], lo["ahb0"]["pool_end"]),
                         (0x10001000, 0x10001400, 0x2007C100, 0x20080000))
    def test_missing_symbol(self):
        with self.assertRaises(ValueError):
            lay.build_layout(MAP.replace("__StackLimit", "__Other"), {})
    def test_dwarf(self):
        self.assertEqual(lpc_dwarf.parse_type_sizes(DWARF.splitlines()), {"Block": 112, "Planner": 168})   # members are ignored, hex sizes parsed


if __name__ == "__main__":
    unittest.main(verbosity=2)
