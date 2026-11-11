import pytest
from llm.conversation import resolve_question

class Model:
    def __init__(self, text):self.text=text
    def generate(self,*args):return {"question":self.text}

@pytest.mark.parametrize("question", ["账号密码没问题，接下来怎么操作客户端？", "已重启两次，不要再让我重启", "Only offline steps, no reinstall."])
def test_original_constraints_survive_lossy_rewrite(question):
    result=resolve_question(Model("VPN 连接失败怎么办？"),question,[{"question":"VPN"}])
    assert question in result
    assert "VPN" in result
    assert len(result)<=1000

def test_oversized_combination_preserves_original_without_cutting():
    question="不允许重装"+"甲"*990
    assert resolve_question(Model("VPN"+"乙"*990),question,[{}])==question

def test_complete_rewrite_is_not_duplicated():
    assert resolve_question(Model("VPN：不要重启"),"不要重启",[{}])=="VPN：不要重启"

def test_first_turn_avoids_model():
    assert resolve_question(None,"不要重启",[])=="不要重启"
