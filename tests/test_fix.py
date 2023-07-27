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


@default_chain.connect(fork=f"{os.getenv('POL_RPC_URL')}@{45204868}")
def test_polygon_before():
    random.seed(44)
    default_chain.set_default_accounts(default_chain.accounts[0])

    PolygonChain = DFXChainConfig(
        pool=Curve(Address("0x2385D7aB31F5a470B1723675846cb074988531da")),
        EURS=IERC20(Address("0xE111178A87A3BFf0c8d18DECBa5798827539Ae99")),
        USDC=IERC20(Address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")),
        USDC_w=Address("0xBA12222222228d8Ba445958a75a0704d566BF2C8"),
        EURS_w=Address("0x38d693ce1df5aadf7bc62595a37d667ad57922e5"),
        add=100,
    )

    DFXFuzzTest(PolygonChain).run(sequences_count=1, flows_count=30)
