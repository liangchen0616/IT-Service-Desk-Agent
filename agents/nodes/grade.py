def make_node(client, public_web=False):
    def grade(state):
        return {"sufficient": client.grade(state["question"], state["documents"], public_web=True) if public_web else client.grade(state["question"], state["documents"])}
    return grade
