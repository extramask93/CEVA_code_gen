import pytest
from decoder import TokenFactory, RegularRegister, VectorRegister, RegularImmediateToken, MultiTokenVPU, ModuRegister
def test_factorytest():
    a= TokenFactory("rA.ui")
    assert isinstance(a,RegularRegister)
    a = TokenFactory("vrB1.s16")
    assert isinstance(a, VectorRegister)
    a = TokenFactory("#uimmA32")
    assert isinstance(a,RegularImmediateToken)
    a = TokenFactory("#immB5")
    assert isinstance(a, RegularImmediateToken)
    a = TokenFactory("(rN.ui+rM.i).di")
    assert isinstance(a,MultiTokenVPU)
    a= TokenFactory("moduA.ui")
    assert isinstance(a, ModuRegister)
    assert a.GetType() == "UI"