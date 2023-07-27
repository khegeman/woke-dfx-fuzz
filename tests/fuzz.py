from woke.testing import *
from woke.testing import Address

from woke.testing.fuzzing import *
from woke.testing.core import default_chain
from woke.testing.fuzzing.fuzz_test import FuzzTest, flow, invariant

from wokelib import given, collector, print_steps
from wokelib import st

from pytypes.protocolv2.src.Curve import Curve
from pytypes.protocolv2.lib.openzeppelincontracts.contracts.token.ERC20.IERC20 import (
    IERC20,
)
from pytypes.tests.contracts.Invariant import Invariant
from pytypes.protocolv2.src.interfaces.IAssimilator import IAssimilator

from dataclasses import dataclass


# send tokens to account for testing
# right now woke doesn't have a deal method that modifies storage
# so I specify a wallet with sufficient assets for the given test
def deal(token, to_, amount, wallet):

    IERC20(token).transfer(to_, amount, from_=wallet)


@dataclass
class DFXChainConfig:
    """Chain specific parameters for test """

    pool: Curve
    EURS: IERC20
    USDC: IERC20

    # wallet addresses
    USDC_w: Address
    EURS_w: Address

    # the fix for the bug seems to be to add 100 EURS to all deposits after the fix
    # this is set to 0 for all tests except for the post fix polygon where it is 100
    add: int


class DFXFuzzTest(FuzzTest):
    _config: DFXChainConfig
    _invariant: Invariant
    _curve: Curve

    def __init__(self, chainConfig: DFXChainConfig):
        self._config = chainConfig
        self._config

    @property
    def curve(self):
        return self._curve

    @collector()
    def pre_sequence(self) -> None:
        # attach to a deployed contract
        self._curve = self._config.pool
        self._invariant = Invariant.deploy()

        self._inv = self._calcInvariant()

    @flow()
    @given(
        amount=st.random_int(
            min=20000000000000000000, max=200000000000000000000, edge_values_prob=0.05
        ),
    )
    @print_steps(do_print=True)
    def deposit(self, amount):
        act = default_chain.accounts[0]

        minQuoteAmount = 0
        minBaseAmount = 0
        maxQuoteAmount = 2852783032400000000000
        maxBaseAmount = 7992005633260983540235600000000
        deadline = 1676706352308

        # save state before the deposit
        usdc_before = self._config.USDC.balanceOf(act)
        eurs_before = self._config.EURS.balanceOf(act)

        (curves, tokens) = self._curve.viewDeposit(amount)

        # deal tokens if we need them to deposit
        # track how much is dealt
        if tokens[0] > 0:
            # adjust the amount needed to deposit if necessary (post fix on polygon)
            add_tokens = self._config.add
            send_tokens = add_tokens + tokens[0]
            if eurs_before < send_tokens:
                deal_amt = send_tokens - eurs_before
                deal(self._config.EURS, act, deal_amt, self._config.EURS_w)

            self._config.EURS.approve(self._curve, send_tokens)
        if tokens[1] > 0:
            if usdc_before < tokens[1]:
                deal(self._config.USDC, act, tokens[1], self._config.USDC_w)

            self._config.USDC.approve(self._curve, tokens[1])
        tx = self._curve.deposit(
            amount,
            minQuoteAmount,
            minBaseAmount,
            maxQuoteAmount,
            maxBaseAmount,
            deadline,
        )

    @flow()
    @given(percent=st.random_float(min=0, max=1))
    @print_steps(do_print=True)
    def withdraw(self, percent):
        act = default_chain.accounts[0]

        balance = self._curve.balanceOf(act)
        if balance > 0:
            to_wd = uint(balance * percent)
            tx = self._curve.withdraw(to_wd, 1676706352308, from_=act)

    # Period is set to 1 to verify the invariant after every flow
    @invariant(period=1)
    def invariant_balances(self) -> None:

        inv = self._calcInvariant()
        assert inv[0] >= self._inv[0]
        self._inv = inv

    def _calcInvariant(self):
        ausdc = IAssimilator(self._config.pool.assimilator(self._config.USDC))
        aerus = IAssimilator(self._config.pool.assimilator(self._config.EURS))

        # this value is from the parameters that constructed the curve

        # this setup is 50/50
        weight = 500000000000000000
        weights = [weight, weight]

        bals = [
            aerus.viewNumeraireBalance(self._config.pool),
            ausdc.viewNumeraireBalance(self._config.pool),
        ]

        (alpha, beta, delta, epsilon, totalsupply) = self._config.pool.viewCurve()

        return self._invariant.compute(
            weights, bals, beta, delta, self._config.pool.totalSupply()
        )
