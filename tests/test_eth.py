from woke.testing import *
from woke.testing import Address


from woke.testing.core import default_chain


from pytypes.protocolv2.src.Curve import Curve
from pytypes.protocolv2.lib.openzeppelincontracts.contracts.token.ERC20.IERC20 import (
    IERC20,
)

from .fuzz import DFXFuzzTest, DFXChainConfig

import os
import random


from dotenv import load_dotenv

load_dotenv()


@default_chain.connect(fork=f"{os.getenv('ETH_RPC_URL')}@{17774255}")
def test_eth():
    random.seed(44)
    default_chain.set_default_accounts(default_chain.accounts[0])

    EthChain = DFXChainConfig(
        pool=Curve(Address("0x8cd86fbC94BeBFD910CaaE7aE4CE374886132c48")),
        EURS=IERC20(Address("0x1aBaEA1f7C830bD89Acc67eC4af516284b1bC33c")),
        USDC=IERC20(Address("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")),
        USDC_w=Address("0xBA12222222228d8Ba445958a75a0704d566BF2C8"),
        EURS_w=Address("0x95DBB3C7546F22BCE375900AbFdd64a4E5bD73d6"),
        add=0,
    )

    DFXFuzzTest(EthChain).run(sequences_count=1, flows_count=30)
