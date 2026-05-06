import pytest
from data_cleaning import parse_cpu, parse_memory, parse_temperature, parse_inventory

def test_parse_cpu():
    assert parse_cpu("5-second CPU: 25.5 %") == 25.5
    assert parse_cpu("CPU utilization: 10%") == 10.0
    assert parse_cpu("invalid") == 0.0

def test_parse_memory():
    raw = """
                Head    Total(b)     Used(b)     Free(b)   Lowest(b)  Largest(b)
    Processor   60000000  2000000000  1000000000  1000000000   999000   999500
    """
    # 1000000000 / 2000000000 * 100 = 50.0
    assert parse_memory(raw) == 50.0

def test_parse_temperature():
    assert parse_temperature("Inlet Temperature: 42.5 °C") == 42.5
    assert parse_temperature("40 C") == 40.0

def test_parse_inventory():
    raw = """
    NAME: "Switch System", DESCR: "Cisco Catalyst 9300-24T"
    PID: C9300-24T         , VID: V01  , SN: FOC2134L05X
    """
    res = parse_inventory(raw)
    assert len(res) == 1
    assert res[0]['pid'] == "C9300-24T"
    assert res[0]['sn'] == "FOC2134L05X"
