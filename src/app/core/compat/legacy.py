class NoOp:
    def __init__(self, *args, **kwargs): pass
    def __call__(self, *args, **kwargs): return self
    def __getattr__(self, name): return self
    def run(self, *args, **kwargs): return {}
    def execute(self, *args, **kwargs): return {}
    def process(self, *args, **kwargs): return {}
    def build(self, *args, **kwargs): return {}
    def mine(self, *args, **kwargs): return {}

FreeStackOrchestrator = NoOp
MinerEngine = NoOp
StaticSiteBuilder = NoOp
FacebookAdMiner = NoOp
CampaignOperator = NoOp
MetaCampaignOperator = NoOp
VideoPipeline = NoOp
PremiumRender = NoOp
