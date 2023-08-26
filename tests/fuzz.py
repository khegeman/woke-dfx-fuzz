from woke.testing import *
from woke.testing import Address

from woke.testing.fuzzing import *
from woke.testing.core import default_chain
from woke.testing.fuzzing.fuzz_test import  flow, invariant

from wokelib.generators.random import st

from pytypes.protocolv2.src.Curve import Curve
from pytypes.protocolv2.lib.openzeppelincontracts.contracts.token.ERC20.IERC20 import (
    IERC20,
)
from pytypes.tests.contracts.Invariant import Invariant
from pytypes.protocolv2.src.interfaces.IAssimilator import IAssimilator

from dataclasses import dataclass

from wokelib.generators.random.fuzz_test import FuzzTest

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

    #random data generators
    st_amount = st.random_int(
            min=20000000000000000000, max=200000000000000000000, edge_values_prob=0.05
        )
    st_percent = st.random_float(min=0, max=1)    

    def __init__(self, chainConfig: DFXChainConfig):
        self._config = chainConfig

    def pre_sequence(self) -> None:
        """Initialize the environment for the contract.

        This function attaches to a deployed contract and calculates the initial invariant.

        Note:
            pre_sequence is called before the first flow to setup the required state
        """
        self._curve = self._config.pool
        self._invariant = Invariant.deploy()
        self._previous_inv = self._calcInvariant()


    @flow()
    def deposit(self, st_amount : uint):
        self._impl_deposit(st_amount)

    @flow()
    def withdraw(self, st_percent : float):        
        self._impl_withdraw(st_percent)

    @invariant(period=1)
    def utility(self) -> None:
        """Check and update the utility invariant
    
        This function asserts that the invariant (as calculated by _calcInvariant) 
        has not decreased. This is to ensure that "utility" in the pool is not decreasing.
    
        Raises:
            AssertionError: If the invariant has decreased.
        """
        inv = self._calcInvariant()
        assert inv >= self._previous_inv, "utility decreased."
        self._previous_inv = inv
    
    
    def _calcInvariant(self):
        """Calculate the invariant for the system.
    
        This function fetches the necessary input values from the DFX smart contracts 
        and calculates the invariant. It considers asset balances, curve parameters, 
        and the total supply of tokens in the pool.
    
        Returns:
            float: The calculated invariant value.
    
        Note:
            This function is intended to be private and should not be called outside 
            of the class it is defined in.
        """
        ausdc = IAssimilator(self._config.pool.assimilator(self._config.USDC))
        aerus = IAssimilator(self._config.pool.assimilator(self._config.EURS))
    
        # This value is from the parameters that constructed the curve
        # This setup is 50/50
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

    def _impl_deposit(self, amount : uint):
        """Deposit tokens into the pool.

        Deposits the specified amount of tokens into the pool and handles any necessary approvals.

        Args:
            amount (uint): The amount to deposit.

        Note:
            This function also calculates the minimum and maximum token amounts and includes logic to deal tokens to the account if needed.
        """     
        act = default_chain.accounts[0]

        minQuoteAmount = 0
        minBaseAmount = 0
        maxQuoteAmount = 2852783032400000000000
        maxBaseAmount = 7992005633260983540235600000000
        deadline = default_chain.blocks[-1].timestamp + 1000

        # save state before the deposit
        usdc_before = self._config.USDC.balanceOf(act)
        eurs_before = self._config.EURS.balanceOf(act)

        (curves, tokens) = self._curve.viewDeposit(amount)

        # deal tokens if we need them to deposit
        # track how much is dealt
        if tokens[0] > 0:
            # adjust the amount needed to deposit if necessary (post fix on polygon)
            # for blocks after the fix we add 100 extra tokens
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

    def _impl_withdraw(self, percent : float):

        """Withdraw tokens from the pool.
    
        Withdraws a specified percentage of tokens from the pool based on the current balance.
    
        Args:
            percent (float): The percentage of staking tokens to withdraw.
    
        Note:
            The function will not proceed if the balance is zero.
        """                
        act = default_chain.accounts[0]
        deadline = default_chain.blocks[-1].timestamp + 1000
        balance = self._curve.balanceOf(act)
        if balance > 0:
            to_wd = uint(balance * percent)
            tx = self._curve.withdraw(to_wd, deadline, from_=act)
