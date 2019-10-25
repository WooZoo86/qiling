#!/usr/bin/env python3
# 
# Cross Platform and Multi Architecture Advanced Binary Emulation Framework
# Built on top of Unicorn emulator (www.unicorn-engine.org) 
#
# LAU kaijern (xwings) <kj@qiling.io>
# NGUYEN Anh Quynh <aquynh@gmail.com>
# DING tianZe (D1iv3) <dddliv3@gmail.com>
# SUN bowen (w1tcher) <w1tcher.bupt@gmail.com>
# CHEN huitao (null) <null@qiling.io>
# YU tong (sp1ke) <spikeinhouse@gmail.com>

import struct
import sys

from unicorn import *
from unicorn.x86_const import *

from capstone import *
from capstone.x86_const import *

from keystone import *
from keystone.x86_const import *

from struct import pack
import os

import string

from qiling.loader.macho import *
from qiling.arch.x86 import *
from qiling.os.ios.arm64_syscall import *
from qiling.os.posix.syscall import *
from qiling.os.ios.syscall import *
from qiling.os.macos.utils import *
from qiling.os.utils import *
from qiling.arch.filetype import *


QL_ARM64_IOS_PREDEFINE_STACKADDRESS = 0x7fffff500000
QL_ARM64_IOS_PREDEFINE_STACKSIZE = 0xa00000
QL_ARM64_IOS_PREDEFINE_MMAPADDRESS = 0x7fffff000000

QL_ARM64_EMU_END = 0xffffffffffffffff


def hook_syscall(uc, ql):
    syscall_num  = uc.reg_read(UC_ARM64_REG_X8)
    param0 = uc.reg_read(UC_ARM64_REG_X0)
    param1 = uc.reg_read(UC_ARM64_REG_X1)
    param2 = uc.reg_read(UC_ARM64_REG_X2)
    param3 = uc.reg_read(UC_ARM64_REG_X3)
    param4 = uc.reg_read(UC_ARM64_REG_X4)
    param5 = uc.reg_read(UC_ARM64_REG_X5)
    pc = uc.reg_read(UC_ARM64_REG_PC)

    ios_syscall_numb_list = []
    ios_syscall_func_list = []

    for i in ARM64_IOS_SYSCALL:
        ios_syscall_numb_list.append(i[0])
        ios_syscall_func_list.append(i[1])

    if any(ios_syscall_numb == syscall_num for ios_syscall_numb in ios_syscall_numb_list):
        ios_syscall_index = ios_syscall_numb_list.index(syscall_num)
        IOS_SYSCALL_FUNC = eval(ios_syscall_func_list[ios_syscall_index])
        try:
            IOS_SYSCALL_FUNC(ql, uc, param0, param1, param2, param3, param4, param5)
        except:
            ql.errmsg = 1
            ql.nprint("SYSCALL: ", ios_syscall_func_list[ios_syscall_index])
            if ql.output in (QL_OUT_DEBUG, QL_OUT_DUMP):
                uc.emu_stop()
                raise
    else:
        ql.nprint("0x%x: syscall number = 0x%x(%d) not implement." %(pc, syscall_num,  (syscall_num -  0x2000000)))
        if ql.output in (QL_OUT_DEBUG, QL_OUT_DUMP):
            uc.emu_stop()


def loader_file(ql):
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    ql.uc = uc
    ql.mmap_start = QL_ARM64_IOS_PREDEFINE_MMAPADDRESS
    if (ql.stack_address == 0):
        ql.stack_address = QL_ARM64_IOS_PREDEFINE_STACKADDRESS
        ql.stack_size = QL_ARM64_IOS_PREDEFINE_STACKSIZE
        uc.mem_map(ql.stack_address, ql.stack_size)
        stack_esp = QL_ARM64_IOS_PREDEFINE_STACKADDRESS + QL_ARM64_IOS_PREDEFINE_STACKSIZE
    envs = env_dict_to_array(ql.env)
    loader = MachoX6664(ql, ql.path, stack_esp, [ql.path], envs, [ql.path], 1)
    loader.MachoX8664()
    ql.stack_address = (int(ql.stack_esp))
    

def loader_shellcode(ql):
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    ql.uc = uc
    if (ql.stack_address == 0):
        ql.stack_address = 0x1000000
        ql.stack_size = 2 * 1024 * 1024
        uc.mem_map(ql.stack_address,  ql.stack_size)
    ql.stack_address = ql.stack_address  + 0x200000 - 0x1000
    ql.uc.mem_write(ql.stack_address, ql.shellcoder)
    

def runner(ql):
    ql.uc.reg_write(UC_X86_REG_RSP, ql.stack_address)
    ql_setup(ql)
    ql.hook_insn(hook_syscall, ql, 1, 0, UC_X86_INS_SYSCALL)
    ql_x8664_setup_gdt_segment_ds(ql, ql.uc)
    ql_x8664_setup_gdt_segment_cs(ql, ql.uc)
    ql_x8664_setup_gdt_segment_ss(ql, ql.uc)

    if (ql.until_addr == 0):
        ql.until_addr = QL_ARM64_EMU_END
    try:
        if ql.shellcoder:
            ql.uc.emu_start(ql.stack_address, (ql.stack_address + len(ql.shellcoder)))
        else:
            ql.uc.emu_start(ql.entry_point, ql.until_addr, ql.timeout)
    except UcError as e:
        if ql.output in (QL_OUT_DEBUG, QL_OUT_DUMP):
            ql.nprint("[+] PC= " + hex(ql.pc))
            ql.show_map_info()

            buf = ql.uc.mem_read(ql.pc, 8)
            ql.nprint("[+] ", [hex(_) for _ in buf])
            ql_hook_code_disasm(ql.uc, ql.pc, 64, ql)
        ql.errmsg = 1
        ql.nprint("%s" % e)  