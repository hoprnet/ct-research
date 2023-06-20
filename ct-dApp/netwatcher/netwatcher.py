from ct.hopr_node import HOPRNode

class NetWatcher(HOPRNode):
    """ Class description."""
    def __init__(self, url: str, key: str):
        """
        Initialisation of the class.
        """
        super().__init__(url, key, 10, '.')
    
    def __str__(self):
        return