import sys
from pathlib import Path
import pyperclip
import functools
from abc import ABCMeta, abstractmethod
from bs4 import BeautifulSoup as bs
from collections import namedtuple
from operator import attrgetter
from enum import Enum
import collections
import copy
from math import log2,ceil
import re
regcnt = 0
immcnt = 0
condcnt = 0
BitLocation = namedtuple("BitLocation", ['bitNr', 'bitShift', 'bitCW'])
def SplitTokens(instString):
    iscond = re.search("\{.*\}",instString)
    cond =""
    if(iscond is not None):
        instString = instString.replace(iscond.group(0),"")
        cond = iscond.group(0)
    all = re.search("^(\S+)\s(.*)",instString)
    registers = all.group(2).split(',')
    for i in range(1,len(registers)):
        if(']' in registers[i] and (not '+' in registers[i])):
            registers[i-1] = registers[i-1].strip('[').strip()
            registers[i] = ' [,'+registers[i]
        i = i+1
    return Instruction(all.group(1),cond,registers)
def TokenFactory(name):
    if (re.search(VectorRegister.GetTokenRegEx(), name) is not None):
        return VectorRegister(name)
    elif(re.search(RegularRegister.GetTokenRegEx(), name) is not None):
        return RegularRegister(name)
    elif(re.search(PredicateVectorRegister.GetTokenRegEx(), name) is not None):
        return PredicateVectorRegister(name)
    elif(re.search(RegularImmediateToken.GetTokenRegEx(), name) is not None):
        return RegularImmediateToken(name)
    elif(re.search(PredicateScalarRegister.GetTokenRegEx(),name) is not None):
        return PredicateScalarRegister(name)
    elif(re.search(ModuRegister.GetTokenRegEx(),name) is not None):
        return ModuRegister(name)
    elif(re.search(MultiTokenVPU.GetTokenRegEx(),name) is not None):
        return MultiTokenVPU(name)
    else:
        print("In supplied html file token with name {0} was found. Sadly There is no support for it.".format(name))
        return NullToken(name)
class Instruction:
    def __init__(self, name, conditionals, registers):
        self.name = name
        self.conditionals = conditionals
        self.registers = registers
        self.regz = []
        for register in self.registers:
            self.regz = self.regz + [TokenFactory(register)]
    def SetHtmlHandle(self,handle):
        self.htmlHandle = handle
    def GetMacro(self):
        lines = []
        if(('|' not in self.conditionals) and ('[' not in self.conditionals)):
            lines = lines + [MnemonicToken(self.name+self.conditionals).GenerateMacro()]
        else:
            lines = lines + [MnemonicToken(self.name).GenerateMacro()]
            condToken = CondToken(self.conditionals)
            condToken.FindBits(copy.copy(self.htmlHandle))
            lines = lines + condToken.GenerateMacro()
        for register in self.regz:
            register.FindBits(copy.copy(self.htmlHandle))
            lines = lines + register.GenerateMacro()
        return lines
class BaseToken:
    __metaclass__ = ABCMeta
    @abstractmethod
    def GenerateMacro(self):
        return "\n"
    @abstractmethod
    def FindBits(self,htmlHandle, findByColor = False):
        found = htmlHandle.find(name = "th",string=self.name.strip())#rvB.i
        sib = found.find_next_sibling('th')
        self.symbol = sib.text
        color = sib.attrs['bgcolor']
        found2 = []
        if(findByColor == True):
            found2 = sib.find_all_next(name = 'th', attrs= {"bgcolor":color},string=re.compile(self.symbol + ".*"))
        else:
            found2 = sib.find_all_next(name = 'th', string = re.compile(self.symbol+".*"))
        if ('p' in self.name):
            found3 = sib.find_next(name='th', string='p')
            if (found3 is None):
                found3 = found.find_previous(name='th', string='p')
            found3 = found3.find_next_sibling('th')
            partColor = found3.attrs['bgcolor']
            part = found3.find_next(name='th', attrs={"bgcolor": partColor}, string=re.compile(self.symbol + ".*"))
            self.partloc = part.find_next(name='th', string=re.compile("(CW|opcode).*"))
            j = 0
            for sibling in part.find_next_siblings(name='th'):
                if (sibling.text == self.partloc.text):
                    break
                else:
                    j = j + 1
            self.partShift = j
            if ('opcode' in self.partloc.text):
                self.partloc = self.partloc.text.split()[0].strip()
            else:
                self.partloc = 'CW' + self.partloc.text.split()[1].strip().strip('0').strip('x').upper()
        Locations = []
        for bit in found2:
            loc = bit.find_next_sibling(name = 'th', string = re.compile("(CW|opcode).*"))
            if(loc is None):
                continue
            i =0
            for sibling in bit.find_next_siblings(name = 'th'):
                if(sibling.text == loc.text):
                    break
                else:
                    i = i+1
            if(loc.text.split()[0].strip() == 'CW'):
                b = BitLocation(bitNr=bit.text.split()[1], bitCW='CW'+loc.text.split()[1].strip().strip('0').strip('x').upper(), bitShift=i)
            else:
                b = BitLocation(bitNr=bit.text.split()[1], bitCW=loc.text.split()[0], bitShift=i)
            self.d[b.bitCW] = self.d[b.bitCW] + [b]
        return
    def isReg(self):
        return False
class NullToken(BaseToken):
    def __init__(self,name):
        self.name = name
    @staticmethod
    def GetTokenRegEx():
        return ".*"
    def FindBits(self,htmlHandle):
        pass
    def GenerateMacro(self):
        return ["NULL TOKEN: {0}".format(self.name)]
class MnemonicToken(BaseToken):
    def __init__(self,mnemo):
        self.mnemo = mnemo
    def GenerateMacro(self):
        return "WRITE_MNEMO(InstPacketInfo_p->operand, \"{0}\");".format(self.mnemo)
class VectorRegister(BaseToken):
    def __init__(self,name):
        self.name = name
        self.shift = 0
        self.mask = 0
        self.type = "VC32"
        self.range = '0'
        self.part = "V_Whole"
        self.partloc = None
        self.partBit = BitLocation(0,0,0)
        self.symbol = 'p0'
        self.realType = None
        self.d = {}
        self.d= collections.defaultdict(list)
    @staticmethod
    def GetTokenRegEx():
        return "^\s*v[rm]?[A-Z0-1]+[plh]?\.\S"
    def GetType(self):
        if (self.realType is None):
            type = self.name.strip().split('.')[1]
            type = 'V' + type.upper()
            return type
        else:
            return 'V'+self.realType
    def isReg(self):
        return True
    def FindBits(self,htmlHandle, findByColor = False):
        found = htmlHandle.find(name = "th",string=self.name.strip())
        if(found is None):
            found = htmlHandle.find(name = "th",string=re.sub("v?","",self.name.strip()))
        sib = found.find_next_sibling('th')
        self.symbol = sib.text
        color = sib.attrs['bgcolor']
        self.range = sib.find_next_sibling(name = 'th').text
        found2 = []
        if(findByColor == True):
            found2 = sib.find_all_next(name = 'th', attrs= {"bgcolor":color}, string = re.compile(self.symbol+".*"))
        else:
            found2 = sib.find_all_next(name = 'th', attrs= {"bgcolor":color},string = re.compile(self.symbol+".*"))
        Locations = []
        if('p' in self.name):
            found3 = sib.find_next(name = 'th', string = 'p')
            if(found3 is None):
                found3 = found.find_previous(name = 'th', string = 'p')
            found3=found3.find_next_sibling('th')
            partColor = found3.attrs['bgcolor']
            part = found3.find_next(name = 'th', attrs= {"bgcolor":partColor}, string = re.compile(self.symbol+".*"))
            self.partloc = part.find_next(name = 'th', string = re.compile("(CW|opcode).*"))
            j=0
            for sibling in part.find_next_siblings(name = 'th'):
                if(sibling.text == self.partloc.text):
                    break
                else:
                    j = j+1
            self.partShift = j
            if('opcode' in self.partloc.text):
                self.partloc = self.partloc.text.split()[0].strip()
            else:
                self.partloc = 'CW' + self.partloc.text.split()[1].strip().strip('0').strip('x').upper()
        for bit in found2:
            loc = bit.find_next_sibling(name = 'th', string = re.compile("(CW|opcode).*"))
            i =0
            for sibling in bit.find_next_siblings(name = 'th'):
                if(sibling.text == loc.text):
                    break
                else:
                    i = i+1
            if(loc.text.split()[0].strip() == 'CW'):
                b = BitLocation(bitNr=bit.text.split()[1], bitCW='CW'+loc.text.split()[1].strip().strip('0').strip('x').upper(), bitShift=i)
            else:
                b = BitLocation(bitNr=bit.text.split()[1], bitCW=loc.text.split()[0], bitShift=i)
            self.d[b.bitCW] = self.d[b.bitCW] + [b]
        return
    def GetPart(self):
        if(re.search("l\.",self.name) is not None):
            return "V_Lower"
        elif(re.search("h\.",self.name) is not None):
            return "V_Higher"
        elif(self.partloc is not None):
            if('opcode' in  self.partloc):
                return "((opcode>>{0})&0x1)?V_Higher:V_Lower".format(self.partShift)
            else:
                return "GetBitFromCW(InstPacketInfo_p,idx,{0},{1})?V_Higher:V_Lower".format(self.partloc,self.partShift)
        else:
            return "V_Whole"
    def GenerateMacro(self):
        global regcnt
        macro = []
        opshift = 0
        opmask = 0
        oplen = 0
        cwtype = 0
        if self.d['opcode']:
            opshift = sorted(self.d['opcode'], key=attrgetter('bitShift'))[0].bitShift
            opmask = pow(2, len(self.d['opcode'])) - 1
            oplen = len(self.d['opcode'])
        for key, value in self.d.items():
            if (key == 'opcode'):
                continue
            else:  # cw part - setup
                cwshift = sorted(self.d[key], key=attrgetter('bitShift'))[0].bitShift
                cwmask = pow(2, len(self.d[key])) - 1
                cwtype = key
                macro = macro + ["SETUP_REG_PART1({0}, {1}, {2}, {3}, {4:#x});".format(regcnt,key,oplen,cwshift,cwmask)]
                regcnt = regcnt +1
        if(re.search("16\.",self.range)is not None):
            macro = macro + ["WRITE_XM6_VR16_47(InstPacketInfo_p->operand, {0}, {1:#x}, {2}, {3});".format(
                opshift, opmask, self.GetType(),self.GetPart())]
        else:
            macro = macro + ["WRITE_XM6_VR0_47(InstPacketInfo_p->operand, {0}, {1:#x}, {2}, {3});".format(
                opshift, opmask, self.GetType(),self.GetPart())]
        if((re.search('1\.',self.name) is not None) and oplen == 0):
            macro[-1] = macro[-1] + "INC_WERT_IF_NO_CW({0},1);".format(cwtype)
        macro[-1] = macro[-1] + "InstPacketInfo_p->operand++;"
        return macro
class RegularRegister(BaseToken):
    def __init__(self,name):
        self.name = name
        self.shift = 0
        self.mask = 0
        self.partloc = None
        self.type = "C"
        self.part = "WHOLE"
        self.realType = None
        self.symbol = 'p0'
        self.d = {}
        self.d= collections.defaultdict(list)
    def isReg(self):
        return True
    @staticmethod
    def GetTokenRegEx():
        return "^\s*r[vA-Z0-1]+[lhp]?\.\S"
    def GetPart(self):
        if(re.search("l\.",self.name) is not None):
            return "LOWER"
        elif(re.search("h\.",self.name) is not None):
            return "HIGHER"
        elif(self.partloc is not None):
            if('opcode' in  self.partloc):
                return "((opcode>>{0})&0x1)?HIGHER:LOWER".format(self.partShift)
            else:
                return "GetBitFromCW(InstPacketInfo_p,idx,{0},{1})?HIGHER:LOWER".format(self.partloc,self.partShift)
        else:
            return "WHOLE"
    def GetType(self):
        if(self.realType is None):
            type = self.name.strip().split('.')[1]
            type = type.upper()
            return type
        else:
            return self.realType
    def FindBits(self,htmlHandle, findByColor = False):
        found = htmlHandle.find(name = "th",string=self.name.strip())#rvB.i
        sib = found.find_next_sibling('th')
        self.symbol = sib.text
        color = sib.attrs['bgcolor']
        found2 = []
        if(findByColor == True):
            found2 = sib.find_all_next(name = 'th', attrs= {"bgcolor":color},string=re.compile(self.symbol + ".*"))
        else:
            found2 = sib.find_all_next(name = 'th', string = re.compile(self.symbol+".*"))
        if ('p' in self.name):
            found3 = sib.find_next(name='th', string='p')
            if (found3 is None):
                found3 = found.find_previous(name='th', string='p')
            found3 = found3.find_next_sibling('th')
            partColor = found3.attrs['bgcolor']
            part = found3.find_next(name='th', attrs={"bgcolor": partColor}, string=re.compile(self.symbol + ".*"))
            self.partloc = part.find_next(name='th', string=re.compile("(CW|opcode).*"))
            j = 0
            for sibling in part.find_next_siblings(name='th'):
                if (sibling.text == self.partloc.text):
                    break
                else:
                    j = j + 1
            self.partShift = j
            if ('opcode' in self.partloc.text):
                self.partloc = self.partloc.text.split()[0].strip()
            else:
                self.partloc = 'CW' + self.partloc.text.split()[1].strip().strip('0').strip('x').upper()
        Locations = []
        for bit in found2:
            loc = bit.find_next_sibling(name = 'th', string = re.compile("(CW|opcode).*"))
            if(loc is None):
                continue
            i =0
            for sibling in bit.find_next_siblings(name = 'th'):
                if(sibling.text == loc.text):
                    break
                else:
                    i = i+1
            if(loc.text.split()[0].strip() == 'CW'):
                b = BitLocation(bitNr=bit.text.split()[1], bitCW='CW'+loc.text.split()[1].strip().strip('0').strip('x').upper(), bitShift=i)
            else:
                b = BitLocation(bitNr=bit.text.split()[1], bitCW=loc.text.split()[0], bitShift=i)
            self.d[b.bitCW] = self.d[b.bitCW] + [b]
        return
    def GenerateMacro(self):
        global regcnt
        macro = []
        opshift = 0
        opmask = 0
        oplen = 0
        if self.d['opcode']:
            opshift = sorted(self.d['opcode'], key=attrgetter('bitShift'))[0].bitShift
            opmask = pow(2, len(self.d['opcode'])) - 1
            oplen = len(self.d['opcode'])
            cwtype = 0
        for key, value in self.d.items():
            if (key == 'opcode'):
                continue
            else:  # cw part - setup
                cwshift = sorted(self.d[key], key=attrgetter('bitShift'))[0].bitShift
                cwmask = pow(2, len(self.d[key])) - 1
                macro = macro + ["SETUP_REG_PART1({0}, {1}, {2}, {3}, {4:#x});".format(regcnt,key,oplen,cwshift,cwmask)]
                cwtype = key
                regcnt = regcnt + 1
        macro = macro + ["WRITE_XM6_R0_63_TYPE_PART(InstPacketInfo_p->operand, {0}, {1:#x}, {2},{3});".format(
                opshift, opmask, self.GetType(),self.GetPart())]
        if((re.search('1\.',self.name) is not None) and oplen == 0):
            macro[-1] = macro[-1] + "INC_WERT_IF_NO_CW({0},1);".format(cwtype)
        macro[-1] = macro[-1] + "InstPacketInfo_p->operand++;"
        return macro
class ModuRegister(BaseToken):
    @staticmethod
    def GetTokenRegEx():
        return "^\s*modu[A-Z0-1]+\.\S"
    def __init__(self,name):
        self.name = name
        self.shift = 0
        self.mask = 0
        self.type = "VC32"
        self.range = '0'
        self.part = "V_Whole"
        self.partloc = None
        self.partBit = BitLocation(0,0,0)
        self.symbol = 'p0'
        self.realType = None
        self.d = {}
        self.d= collections.defaultdict(list)
    def GetType(self):
        if(self.realType is None):
            type = self.name.strip().split('.')[1]
            type = type.upper()
            return type
        else:
            return self.realType
    def GenerateMacro(self):
        global regcnt
        macro = []
        opshift = 0
        opmask = 0
        oplen = 0
        if self.d['opcode']:
            opshift = sorted(self.d['opcode'], key=attrgetter('bitShift'))[0].bitShift
            opmask = pow(2, len(self.d['opcode'])) - 1
            oplen = len(self.d['opcode'])
            cwtype = 0
        for key, value in self.d.items():
            if (key == 'opcode'):
                continue
            else:  # cw part - setup
                cwshift = sorted(self.d[key], key=attrgetter('bitShift'))[0].bitShift
                cwmask = pow(2, len(self.d[key])) - 1
                macro = macro + [
                    "SETUP_REG_PART1({0}, {1}, {2}, {3}, {4:#x});".format(regcnt, key, oplen, cwshift, cwmask)]
                cwtype = key
                regcnt = regcnt + 1
        macro = macro + ["WRITE_XM6_modu(InstPacketInfo_p->operand,{0},{1},{2});".format(
            opshift, opmask, self.GetType())]
        if ((re.search('1\.', self.name) is not None) and oplen == 0):
            macro[-1] = macro[-1] + "INC_WERT_IF_NO_CW({0},1);".format(cwtype)
        macro[-1] = macro[-1] + "InstPacketInfo_p->operand++;"
        return macro
class PredicateVectorRegister(BaseToken):
    def __init__(self, name):
        self.name = name
        self.shift = 0
        self.mask = 0
        self.type = "VPRB32"
        self.symbol = 'p0'
        self.d = {}
        self.d = collections.defaultdict(list)
    @staticmethod
    def GetTokenRegEx():
        return "^\s*\[?\s*?,?\s*\??vpr[vA-Z0-1]+\.\S"
    def GetType(self):
        type = self.name.strip().split('.')[1]
        type = type.upper().strip(']')
        if('?' in  self.name):
            return 'QVPR'+type
        else:
            return 'VPR'+type

    def FindBits(self, htmlHandle):
        found = htmlHandle.find(name="th", string=self.name.strip())  # rvB.i
        if(found is None):
            found = htmlHandle.find(name="th", string=self.name.strip().strip('[').strip(']').strip(',').strip())
        sib = found.find_next_sibling('th')
        self.symbol = sib.text
        found2 = sib.find_all_next(name='th', string=re.compile(self.symbol + ".*"))
        Locations = []
        for bit in found2:
            loc = bit.find_next_sibling(name='th', string=re.compile("\s*(CW|opcode).*"))
            i = 0
            for sibling in bit.find_next_siblings(name='th'):
                if (sibling.text == loc.text):
                    break
                else:
                    i = i + 1
            b = 0
            if(loc.text.split()[0].strip() == 'CW'):
                b = BitLocation(bitNr=bit.text.split()[1], bitCW='CW'+loc.text.split()[1].strip().strip('0').strip('x').upper(), bitShift=i)
            else:
                b = BitLocation(bitNr=bit.text.split()[1], bitCW=loc.text.split()[0], bitShift=i)
            self.d[b.bitCW] = self.d[b.bitCW] + [b]
        return

    def GenerateMacro(self):
        global regcnt
        macro = []
        opshift = 0
        opmask = 0
        oplen = 0
        if self.d['opcode']:
            opshift = sorted(self.d['opcode'], key=attrgetter('bitShift'))[0].bitShift
            opmask = pow(2, len(self.d['opcode'])) - 1
            oplen = len(self.d['opcode'])
        for key, value in self.d.items():
            if (key == 'opcode'):
                continue
            else:  # cw part - setup
                cwshift = sorted(self.d[key], key=attrgetter('bitShift'))[0].bitShift
                cwmask = pow(2, len(self.d[key])) - 1
                macro = macro + [
                    "SETUP_REG_PART1({0}, {1}, {2}, {3}, {4:#x});".format(regcnt, key, oplen, cwshift, cwmask)]
                regcnt = regcnt + 1
        macro = macro + [
            "WRITE_XM6_prX(InstPacketInfo_p->operand, {0}, {1:#x}, {2}); InstPacketInfo_p->operand++;".format(
                opshift, opmask, self.GetType())]
        return macro
class PredicateScalarRegister(BaseToken):
    def __init__(self, name):
        self.name = name
        self.shift = 0
        self.mask = 0
        self.type = "xB"
        self.symbol = 'p0'
        self.d = {}
        self.d = collections.defaultdict(list)
    @staticmethod
    def GetTokenRegEx():
        return "^\s*\[?,?\??pr[vA-Z0-1]+\.\S"
    def GetType(self):
        type = self.name.strip().split('.')[1]
        type = type.upper().strip(']')
        if('?' in  self.name):
            return 'QVPR'+type
        else:
            return 'VPR'+type
    def FindBits(self, htmlHandle):
        found = htmlHandle.find(name="th", string=self.name.strip().strip('[').strip(']').strip(','))  # rvB.i
        sib = found.find_next_sibling('th')
        self.symbol = sib.text
        found2 = sib.find_all_next(name='th', string=re.compile(self.symbol + ".*"))
        Locations = []
        for bit in found2:
            loc = bit.find_next_sibling(name='th', string=re.compile("\s*(CW|opcode).*"))
            i = 0
            for sibling in bit.find_next_siblings(name='th'):
                if (sibling.text == loc.text):
                    break
                else:
                    i = i + 1
            b = 0
            if(loc.text.split()[0].strip() == 'CW'):
                b = BitLocation(bitNr=bit.text.split()[1], bitCW='CW'+loc.text.split()[1].strip().strip('0').strip('x').upper(), bitShift=i)
            else:
                b = BitLocation(bitNr=bit.text.split()[1], bitCW=loc.text.split()[0], bitShift=i)
            self.d[b.bitCW] = self.d[b.bitCW] + [b]
        return

    def GenerateMacro(self):
        global regcnt
        macro = []
        opshift = 0
        opmask = 0
        oplen = 0
        if self.d['opcode']:
            opshift = sorted(self.d['opcode'], key=attrgetter('bitShift'))[0].bitShift
            opmask = pow(2, len(self.d['opcode'])) - 1
            oplen = len(self.d['opcode'])
        for key, value in self.d.items():
            if (key == 'opcode'):
                continue
            else:  # cw part - setup
                cwshift = sorted(self.d[key], key=attrgetter('bitShift'))[0].bitShift
                cwmask = pow(2, len(self.d[key])) - 1
                macro = macro + [
                    "SETUP_REG_PART1({0}, {1}, {2}, {3}, {4:#x});".format(regcnt, key, oplen, cwshift, cwmask)]
                regcnt = regcnt + 1
        macro = macro + [
            "WRITE_XM6_prX(InstPacketInfo_p->operand, {0}, {1:#x}, xB); InstPacketInfo_p->operand++;".format(
                opshift, opmask)]
        return macro
class RegularImmediateToken(BaseToken):
    class ImmType(Enum):
        Nuimm = 1
        Nimm = 2
    def __init__(self, name):
        self.name = name
        self.shift = 0
        self.mask = 0
        if('u' in name):
            self.type = self.ImmType.Nuimm
        else:
            self.type = self.ImmType.Nimm
        self.symbol = 'p0'
        self.d = {}
        self.d = collections.defaultdict(list)
    @staticmethod
    def GetTokenRegEx():
        return "^\s*#u?imm[A-Z0-1]+"
    def FindBits(self, htmlHandle, findByColor = False):
        found = htmlHandle.find(name="th", string=re.compile('\s*'+self.name.strip()+'\s*'))
        if(found is None):
            temp = re.sub("[A-Z]?","",self.name)
            found = htmlHandle.find(name="th", string=re.compile('\s*' + temp.strip().strip('#') + '\s*'))
        sib = found.find_next_sibling('th')
        self.symbol = sib.text
        color = sib.attrs['bgcolor']
        found2 = []
        if (findByColor == True):
            found2 = sib.find_all_next(name='th', attrs={"bgcolor": color}, string=re.compile(self.symbol + ".*"))
        else:
            found2 = sib.find_all_next(name='th', string=re.compile(self.symbol + ".*"))
        Locations = []
        for bit in found2:
            loc = bit.find_next_sibling(name='th', string=re.compile("\s*(CW|opcode).*"))
            i = 0
            for sibling in bit.find_next_siblings(name='th'):
                if (sibling.text == loc.text):
                    break
                else:
                    i = i + 1
            b = 0
            if(loc.text.split()[0].strip() == 'CW'):
                b = BitLocation(bitNr=bit.text.split()[1], bitCW='CW'+loc.text.split()[1].strip().strip('0').strip('x').upper(), bitShift=i)
            else:
                b = BitLocation(bitNr=bit.text.split()[1], bitCW=loc.text.split()[0], bitShift=i)
            self.d[b.bitCW] = self.d[b.bitCW] + [b]
        return
    def mycompare(item1,item2):
        if(item1.bitCW == 'CW7' and item2.bitCW == 'CWF8'):
            return -1
        elif(item1.bitCW == 'CWF8' and item2.bitCW == 'CW7'):
            return 1
        else:
            return 0
    def GenerateMacro(self):
        global regcnt
        global immcnt
        macro = []
        allvalues = []
        for key, value in self.d.items():
            allvalues = allvalues + value
        allvalues = sorted(allvalues, key= lambda x:int(x.bitNr))
        allvalues = sorted(allvalues, key=functools.cmp_to_key(RegularImmediateToken.mycompare))
        cnt = 1
        firstBit = BitLocation(0,0,0)
        for i in range(0,len(allvalues)):
            if(((i == len(allvalues)-1)) or (abs(int(allvalues[i].bitNr) - int(allvalues[i+1].bitNr))>1) or
                    (allvalues[i].bitCW != allvalues[i+1].bitCW) or
                    (abs(allvalues[i].bitShift - allvalues[i+1].bitShift)>1) or
                    (i == len(allvalues)-2)):
                if(cnt == 1):
                    firstBit = allvalues[i]
                if(i == len(allvalues) - 2):
                    cnt = cnt+1
                if((i==len(allvalues)-2) and (allvalues[i].bitCW != allvalues[i+1].bitCW)):
                    cnt = cnt-1
                if((i==len(allvalues)-1) and not(allvalues[-1].bitCW != allvalues[-2].bitCW) and (abs(allvalues[-1].bitShift - allvalues[-2].bitShift)==1)):
                    continue
                cwmask = pow(2, cnt)-1
                cwshift = firstBit.bitShift
                key = allvalues[i].bitCW
                macro = macro + ["SETUP_IMM_PART1({0}, {1}, {2}, {3:#x});".format(immcnt, key, cwshift, cwmask)]
                cnt = 1
            else:
                if(cnt == 1):
                    firstBit = allvalues[i]
                cnt = cnt+1
        if(self.type == self.ImmType.Nuimm):
            macro = macro + ["WRITE_XM6_uimm_ashex_new(InstPacketInfo_p->operand, 0, 0); InstPacketInfo_p->operand++;"]
        else:
            macro = macro + ["WRITE_XM6_imm_new(InstPacketInfo_p->operand, 0, 0); InstPacketInfo_p->operand++;"]
        immcnt = immcnt + 1
        return macro
class CondToken(BaseToken):
    def __init__(self, name):
        self.name = name
        self.shift = 0
        self.mask = 0
        self.symbol = 'p0'
        self.d = {}
        self.d= collections.defaultdict(list)
    def FindBits(self,htmlHandle):
        found = htmlHandle.find(name="th", string=self.name.strip())
        if(found is None):
            found = htmlHandle.find(name="th", string=self.name.strip().strip('{').strip('}').strip('[').strip(']'))
        if(found is not None):
            sib = found.find_next_sibling('th')
            self.symbol = sib.text
            found2 = sib.find_all_next(name='th', string=re.compile(self.symbol + ".*"))
            Locations = []
            for bit in found2:
                loc = bit.find_next_sibling(name='th', string=re.compile("(CW|opcode).*"))
                i = 0
                for sibling in bit.find_next_siblings(name='th'):
                    if (sibling.text == loc.text):
                        break
                    else:
                        i = i + 1
                if (loc.text.split()[0].strip() == 'CW'):
                    b = BitLocation(bitNr=bit.text.split()[1],
                                    bitCW='CW' + loc.text.split()[1].strip().strip('0').strip('x').upper(), bitShift=i)
                else:
                    b = BitLocation(bitNr=bit.text.split()[1], bitCW=loc.text.split()[0], bitShift=i)
                self.d[b.bitCW] = self.d[b.bitCW] + [b]
        else:
            temp = self.name.split(',')
            for t in temp:
                t = re.sub("[\[\]\{\}]","",t)
                found = htmlHandle.find(name="th", string=re.sub("[\[\]\{\}]","",t))
                sib = found.find_next_sibling('th')
                self.symbol = sib.text
                found2 = sib.find_all_next(name='th', string=re.compile(self.symbol + ".*"))
                Locations = []
                for bit in found2:
                    loc = bit.find_next_sibling(name='th', string=re.compile("(CW|opcode).*"))
                    if(loc is None):
                        break
                    i = 0
                    for sibling in bit.find_next_siblings(name='th'):
                        if(sibling is None or loc is None):
                            break
                        if (sibling.text == loc.text):
                            break
                        else:
                            i = i + 1
                    if (loc.text.split()[0].strip() == 'CW'):
                        b = BitLocation(bitNr=bit.text.split()[1],
                                        bitCW='CW' + loc.text.split()[1].strip().strip('0').strip('x').upper(), bitShift=i)
                    else:
                        b = BitLocation(bitNr=bit.text.split()[1], bitCW=loc.text.split()[0], bitShift=i)
                    self.d[b.bitCW] = self.d[b.bitCW] + [b]
        return
    def GenerateMacro(self):
        global condcnt
        conditionals = self.name.strip('{').strip('}').strip().split(',')
        isconst = False
        macro = []
        prevLen = 0
        for i in range(0,len(conditionals)):
            pieces = conditionals[i].split('|')
            initialPiecesLen = len(pieces)
            if( ']' in pieces[0]):
                pieces.insert(0,'NONE')
            else:
                if(re.search(".*\|.*",self.name)==None):
                    isconst = True
            pieces.extend(['NONE','NONE','NONE','NONE','NONE','NONE'])
            if(len(conditionals)>1 and i==0):
                bracket = 'OPEN_BRACKET'
            elif(len(conditionals)>1 and i==len(conditionals)-1):
                bracket = 'CLOSE_BRACKET'
            elif(len(conditionals)>1):
                bracket ='NONE_BRACKET'
            else:
                bracket = 'BOTH_BRACKETS'
            for i in range(0,len(pieces)):
                pieces[i] = pieces[i].strip().upper()
                pieces[i] = pieces[i].replace('[','').replace(']','')
            allvalues = []
            for key, value in self.d.items():
                allvalues = allvalues + value
            allvalues = sorted(allvalues, key=lambda x: int(x.bitNr))
            cnt = 1
            firstBit = BitLocation(0, 0, 0)
            if(len(allvalues)==1):
                allvalues = allvalues + [BitLocation(0,0,0)]
            for i in range(0, len(allvalues) - 1):
                if ((abs(int(allvalues[i].bitNr) - int(allvalues[i + 1].bitNr)) > 1) or (
                        allvalues[i].bitCW != allvalues[i + 1].bitCW) or (
                        abs(allvalues[i].bitShift - allvalues[i + 1].bitShift) > 1) or (i == len(allvalues) - 2)):
                    if (cnt == 1):
                        firstBit = allvalues[i+prevLen]
                    if (i == len(allvalues) - 2):
                        cnt = cnt + 1
                    foo = pow(2,ceil(log2(initialPiecesLen)))-1
                    if(foo == 0):
                        foo=1
                    prevLen = ceil(log2(initialPiecesLen))
                    cwmask = foo
                    if(isconst):
                        cwmask = 0
                        isconst = False
                    cwshift = firstBit.bitShift
                    key = allvalues[i].bitCW
                    if('opcode' not in key):
                        macro = macro + ["if (GetLinkedCW(InstPacketInfo_p, idx, {0}) != NULL) {{".format(key)]
                    macro = macro + ["SETUP_COND_PART({0}, {1}, {2}, {3}, {4}, {5}, {6}, {7}, {8},{9:#x});".format(condcnt,pieces[0],pieces[1],pieces[2], pieces[3], pieces[4],pieces[5],key,cwshift,cwmask)]
                    macro = macro + ["WRITE_XM6_cond_new(InstPacketInfo_p->operand, {0});InstPacketInfo_p->operand++;".format(bracket)]
                    if('opcode' not in key):
                        macro = macro + ['}']
                    condcnt = condcnt + 1
                    prevLen = bin(cwmask).count('1')
                    cnt = 1
                else:
                    if (cnt == 1):
                        firstBit = allvalues[i+prevLen]
                cnt = cnt + 1

        return macro
class MultiTokenVPU(BaseToken):
    def __init__(self, name):
        self.name = name
        self.wholeType = re.search("\)\.([A-Za-z0-9]+)[\[\s$]*",name).group(1)
        self.realType = self.wholeType
        self.offsetImmediate = re.search("\[\+(\S+)\]",name)
        if(self.offsetImmediate is not None):
            self.offsetImmediate = self.offsetImmediate.group(1)
        self.others = re.search("\((.*)\)",name).group(1).split('+')
        for i in range(0,len(self.others)):
            self.others[i] = self.others[i].strip()
        self.shift = 0
        self.mask = 0
        self.html = 0
        self.symbol = 'p0'
        self.d = {}
        self.d = collections.defaultdict(list)
    @staticmethod
    def GetTokenRegEx():
        return "^\s*\(.*\)\.\S+"
    def FindBits(self, htmlHandle):
        self.html = copy.copy(htmlHandle)
        return
    def isReg(self):
        return True
    def GenerateMacro(self):
        global regcnt
        global immcnt
        macro = []
        macro = macro + ["OPEN_BRACKET_XM6;"]
        for other in self.others:
            token = TokenFactory(other)
            token.FindBits(self.html, findByColor = True)
            macro = macro + token.GenerateMacro()
            macro = macro + ['PLUS_XM6;']
        macro = macro[:-1]
        macro = macro + ['CLOSE_BRACKET_XM6; TYPE_XM6({0});'.format(self.realType.upper())]
        if(self.offsetImmediate is not None):
            macro = macro + ['PLUS_XM6;']
            token = RegularImmediateToken('Post mode imm ')
            token.FindBits(self.html, findByColor = True)
            macro = macro + token.GenerateMacro()
        return macro

def LoadCorrespondingCmm(htmlName):
    instDir = Path().absolute().parts[-1]
    moduleDir = Path().absolute().parts[-2]
    preDir = Path().absolute().parts[:-3]
    a = ""
    for part in preDir:
        a = a + str(part)
        if('\\' not in str(part)):
            a=a+'\\'
    cmmname = htmlName.replace("html","cmm")
    cmmpath = a+"cmm\\"+str(moduleDir)+'\\'+str(instDir)+'\\'+cmmname
    cmm = open(cmmpath,'r')
    lineOK = ''
    for i,line in enumerate(cmm):
        if(i == 7):
            lineOK = line
            break
    inst = line.split(';')[1].strip()
    toreplace1 = re.search('^(\S+\s).*',inst).group(1)
    inst = inst.replace(toreplace1,"")
    if(re.search('({.*})',inst)is not None):
        toreplace1 = re.search('({.*})', inst).group(1)
        inst = inst.replace(toreplace1,"")
    registers = inst.split(',')
    for i in range(0,len(registers)):
        registers[i] = registers[i].strip()
    cmm.close()
    return registers
if __name__ == "__main__":
    debug = True
    arek = False
    htmlName = "LS1.vst{sat}moduA.ui,vrB.i8,(rN.ui).s8[+pm][,vprX.b8][,prP.b].html"
    if(not debug):
        htmlName = sys.argv[1]#
    if(not debug and not arek):
        cmmregs = LoadCorrespondingCmm(htmlName)
    with open(htmlName, 'r') as htmlFile:
        content = htmlFile.read()
    soup = bs(content,"html.parser")
    header = soup.find_all("h2")
    instr = SplitTokens(header[0].text)
    instr.SetHtmlHandle(soup)
    if(not debug and not arek):
        for i in range(0,len(instr.regz)):
            if(instr.regz[i].isReg() and not isinstance(instr.regz[i],MultiTokenVPU)):
                if(instr.regz[i].name.strip().split('.')[1] == cmmregs[i].split('.')[1]):
                    pass
                else:
                    instr.regz[i].realType = cmmregs[i].split('.')[1].upper()
            if (instr.regz[i].isReg() and isinstance(instr.regz[i], MultiTokenVPU)):
                if (instr.regz[i].name.strip().split(').')[1] == cmmregs[i].split(').')[1]):
                    pass
                else:
                    instr.regz[i].realType = re.sub("\+.*","",cmmregs[i].split(').')[1].upper())
    str = "\t\t/*{0}*/\n".format(header[0].text)
    for macro in instr.GetMacro():
        str = str+macro+'\n'
    str = str.strip()
    pyperclip.copy(str)
    print(instr.GetMacro())

