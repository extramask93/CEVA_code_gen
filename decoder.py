import sys
from abc import ABCMeta, abstractmethod
from bs4 import BeautifulSoup as bs
from collections import namedtuple
import re
BitLocation = namedtuple("BitLocation","bitNr","bitPos","BitLoc")
def SplitTokens(instString):
    iscond = re.search("\{.*\}",instString)
    cond =""
    if(iscond is not None):
        instString = instString.replace(iscond.group(0),"")
        cond = iscond.group(0)
    instString = instString.replace('[','').replace(']','')
    all = re.search("^(\S+)\s(.*)",instString)
    return Instruction(all.group(1),cond,all.group(2).split(','))
def TokenFactory(name):
    if (re.search(VectorRegister.GetTokenRegEx(), name) is not None):
        return VectorRegister(name)
    else:
        return BaseToken()
class Instruction:
    def __init__(self, name, conditionals, registers):
        self.name = name
        self.conditionals = conditionals
        self.registers = registers
    def SetHtmlHandle(self,handle):
        self.htmlHandle = handle
    def GetMacro(self):
        lines = []
        lines = lines + [MnemonicToken(self.name).GenerateMacro()]
        for register in self.registers:
            token = TokenFactory(register)
            token.FindBits(self.htmlHandle)
            lines = lines + [token.GenerateMacro()]
        return lines
class BaseToken:
    __metaclass__ = ABCMeta
    @abstractmethod
    def GenerateMacro(self):
        return "\n"
    @abstractmethod
    def FindBits(self,htmlHandle):
        pass
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
        self.part = "V_Whole"
        self.symbol = 'p0'
    @staticmethod
    def GetTokenRegEx():
        return "^\s*v[A-Z0-1]+\.\S"
    def FindBits(self,htmlHandle):
        found = htmlHandle.find(name = "th",string=self.name)
        sib = found.find_next_sibling('th')
        self.symbol = sib.text
        found2 = sib.find_all_next(name = 'th', string = re.compile(self.symbol+".*"))
        Locations = []
        for bit in found2:
            loc = bit.find_next_sibling(name = 'th', string = re.compile("(CW|opcode).*"))
            i =0
            for sibling in bit.find_next_siblings(name = 'th'):
                if(sibling.text == loc.text):
                    break
                else:
                    i = i+1
            BitLocation(bit.text.spilt()[1],loc.text.split()[0],i)

        return
    def GenerateMacro(self):
        return "WRITE_XM6_VR0_47(InstPacketInfo_p->operand, {0}, {1}, {2}, {3}); InstPacketInfo_p->operand++;".format(
            self.shift,self.type,self.mask,self.part
        )



htmlName = "VPU0.vcmpvA.l4,rvB.i,rvC.i,vprZ.b4.html"#sys.argv[1]
with open(htmlName, 'r') as htmlFile:
    content = htmlFile.read()
soup = bs(content,"html.parser")
header = soup.find_all("h2")
instr = SplitTokens(header[0].text)
instr.SetHtmlHandle(soup)
print(instr.GetMacro())

