def make_node(client):
    def grade(state):
        return {"sufficient": client.grade(state["question"], state["documents"])}
    return grade
