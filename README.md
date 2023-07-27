# Intro

While reading this [article](https://medium.com/immunefi/dfx-finance-rounding-error-bugfix-review-17ba5ffb4114) about a white hat on [ImmunFi](https://immunefi.com) that found a bug related to incorrect calculations when a token has 2 decimals, I immediately had a thought that this type of vulnerability should be able to be detected by fuzz tests against the protol.  I used the [Woke](https://ackeeblockchain.com/woke/docs/latest/) Python framework for testing smart contracts.

# Protocol Invariant For DFX Finance

To develop the tests, I first had to determine what the invariants are for the protocol.  The fuzz test will then be setup to verify that the invariant holds follow each transaction that is executed. 



The invariant of the protocol is given in the shell procotol [paper](https://github.com/cowri/shell-solidity-v1/blob/master/Shell_White_Paper_v1.0.pdf) in equation 5, which defines an equation for utility.  This utility should either increase or stay the same after each transaction.  




I could not find an exposed method to compute the current invariant, the functions that are needed are defined in the [Curve Math](https://github.com/dfx-finance/protocol-v2/blob/main/src/CurveMath.sol) contract.  To build a quick test, I just copied these functions to a new contract.  



```solidity
contract Invariant {

    //These calculations come from CurveMath
    //see https://github.com/cowri/shell-solidity-v1/blob/master/Shell_White_Paper_v1.0.pdf
    using ABDKMath64x64 for int128;
    using ABDKMath64x64 for uint256;

    function calculateFee(
        int128 _gLiq,
        int128[] memory _bals,
        int128 _beta,
        int128 _delta,
        int128[2] memory _weights
    ) internal pure returns (int128 psi_) {
        uint256 _length = _bals.length;

        for (uint256 i = 0; i < _length; i++) {
            int128 _ideal = _gLiq.mul(_weights[i]);
            psi_ +=  calculateMicroFee(_bals[i], _ideal, _beta, _delta);
        }
    }
    int128 private constant ONE = 0x10000000000000000;
    int128 private constant MAX = 0x4000000000000000; // .25 in layman's terms
    function calculateMicroFee(
        int128 _bal,
        int128 _ideal,
        int128 _beta,
        int128 _delta
    ) private pure returns (int128 fee_) {
        if (_bal < _ideal) {
            int128 _threshold = _ideal.mul(ONE - _beta);

            if (_bal < _threshold) {
                int128 _feeMargin = _threshold - _bal;

                fee_ = _feeMargin.mul(_delta);
                fee_ = fee_.div(_ideal);

                if (fee_ > MAX) fee_ = MAX;

                fee_ = fee_.mul(_feeMargin);
            } else fee_ = 0;
        } else {
            int128 _threshold = _ideal.mul(ONE + _beta);

            if (_bal > _threshold) {
                int128 _feeMargin = _bal - _threshold;

                fee_ = _feeMargin.mul(_delta);
                fee_ = fee_.div(_ideal);

                if (fee_ > MAX) fee_ = MAX;

                fee_ = fee_.mul(_feeMargin);
            } else fee_ = 0;
        }
    }

    /**
        Expose invariant calculations to the fuzzer
     */
    function compute(uint256[2] memory _weights, int128[] memory _bals,uint256 _beta, uint256 _delta,uint256 _totalSupply) external pure returns (uint256 invariant_,int128 fee_,int128 g_, int128 totalShells_) {
        

        int128 __weight0 = _weights[0].divu(1e18).add(uint256(1).divu(1e18));
        int128 __weight1 = _weights[1].divu(1e18).add(uint256(1).divu(1e18));

        int128 beta = (_beta + 1).divu(1e18);        
        int128 delta = _delta.divu(1e18); 
        int128[2] memory weights = [__weight0,__weight1];
        totalShells_ = _totalSupply.divu(1e18);
        g_ = 0;
        for (uint i =0; i< _bals.length; ++i) {
            g_ += _bals[i];
        }
        
        fee_ = calculateFee(g_, _bals, beta, delta, weights);
        int128 r = (g_ - fee_).div(totalShells_);
        invariant_ = uint256(int256(r));
        
    }
}
```



# Simple Fuzz Test

Figuring out how to implement the invariant calculation ended up being the hardest part of the developing the fuzz test.  Using the above contract, in woke I defined an invariant that is checked after each flow (or step) of the stateful fuzz test.  This function computes the value for the invariant and verifies that the new value is greater than or equal to the previous value.  This follows the definition of the variant given in the paper.



```python
    #Period is set to 1 to verify the invariant after every flow
    @invariant(period=1) 
    def invariant_balances(self) -> None:

        inv = self._calcInvariant()
        assert inv[0] >= self._inv[0]
        self._inv = inv
    
    def _calcInvariant(self):
        ausdc = IAssimilator(self._config.pool.assimilator(self._config.USDC))
        aerus = IAssimilator(self._config.pool.assimilator(self._config.EURS))        

        #this value is from the parameters that constructed the curve

        #this setup is 50/50
        weight = 500000000000000000
        weights = [weight,weight]

        bals = [aerus.viewNumeraireBalance(self._config.pool),ausdc.viewNumeraireBalance(self._config.pool) ]

        (alpha,beta,delta,epsilon,totalsupply) = self._config.pool.viewCurve()

        return self._invariant.compute(weights, bals, beta,delta,self._config.pool.totalSupply())    
```



## Deposit

The first flow I implemented added was for deposits.  This method computes uses `viewDeposit` to compute how many of the two tokens in the pool we will need to complete the deposit.  The tokens are then transfered to the user if necessary so that the deposit can be completed.



```python
    @flow()        
    def deposit(self, amount : uint):
        act = default_chain.accounts[0]

        minQuoteAmount = 0
        minBaseAmount = 0
        maxQuoteAmount = 2852783032400000000000
        maxBaseAmount = 7992005633260983540235600000000
        deadline = 1676706352308

        #save state before the deposit
        usdc_before = self._config.USDC.balanceOf(act)
        eurs_before = self._config.EURS.balanceOf(act)
        
        (curves, tokens) = self._curve.viewDeposit(amount)
        
        #deal tokens if we need them to deposit
        #track how much is dealt
        if tokens[0] > 0:
            #adjust the amount needed to deposit if necessary (post fix on polygon)
            add_tokens = self._config.add
            send_tokens = add_tokens + tokens[0]
            if eurs_before < send_tokens:
                deal_amt = send_tokens - eurs_before
                deal(self._config.EURS, act, deal_amt,self._config.EURS_w)        

            self._config.EURS.approve(self._curve, send_tokens)     
        if tokens[1] > 0:
            if usdc_before < tokens[1]:                
                deal(self._config.USDC, act, tokens[1],self._config.USDC_w)   
   
            self._config.USDC.approve(self._curve,  tokens[1])        
        tx = self._curve.deposit(amount, minQuoteAmount, minBaseAmount, maxQuoteAmount, maxBaseAmount, deadline)
```



I created a similar simple flow for withdraws that removes a percentage of the users position in the pool. 



# Running the fuzz test

I looked up all the contract addresses on Polygon as well as a block number from before the fix was applied and then configured a fuzz test. 



```python
@default_chain.connect(
    fork=f"{os.getenv('POL_RPC_URL')}@{39422000}" 
)
def test_polygon_before():    
    random.seed(44)
    default_chain.set_default_accounts(default_chain.accounts[0])

    PolygonChain = DFXChainConfig(pool = Curve(Address("0x2385D7aB31F5a470B1723675846cb074988531da")), EURS = IERC20(Address("0xE111178A87A3BFf0c8d18DECBa5798827539Ae99")), USDC = IERC20(Address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")),
                              USDC_w=Address("0xBA12222222228d8Ba445958a75a0704d566BF2C8"), EURS_w=Address("0x38d693ce1df5aadf7bc62595a37d667ad57922e5"), add = 0)

    DFXFuzzTest(PolygonChain).run(sequences_count=1, flows_count=30)
```

`DFXChainConfig` is a small class I created that is used to store the chain specific parameters, this allows me to use the same Fuzz test to run on Ethereum mainnet.  



Upon running the test, it immediately fails on the first deposit.  


```
 woke test tests/test_polygon.py 
```

```
self = <tests.fuzz.DFXFuzzTest object at 0x7f419c2ec2b0>

    @invariant(period=1)
    def invariant_balances(self) -> None:
    
        inv = self._calcInvariant()
>       assert inv[0] >= self._inv[0]
E       AssertionError

tests/fuzz.py:109: AssertionError
=============================================================================================================== short test summary info ===============================================================================================================
FAILED tests/test_polygon.py::test_polygon_before - AssertionError
```



To verify the fix, I setup a 2nd configuration file on a recent block number `45204868`.  



```
 woke test tests/test_fix.py 
```



This test runs a sequence of deposit and withdraw flows without violating the invariant.

```
seq: 0 flow: 0 flow name: deposit flow parameters: {'amount': 59045400657728007840}
seq: 0 flow: 1 flow name: deposit flow parameters: {'amount': 188172519178507717912}
seq: 0 flow: 2 flow name: deposit flow parameters: {'amount': 141582438149601136709}
seq: 0 flow: 3 flow name: withdraw flow parameters: {'percent': 0.6700338000515094}
seq: 0 flow: 4 flow name: deposit flow parameters: {'amount': 68279186793786570705}
seq: 0 flow: 5 flow name: deposit flow parameters: {'amount': 200000000000000000000}
seq: 0 flow: 6 flow name: deposit flow parameters: {'amount': 111672339507648347502}
seq: 0 flow: 7 flow name: deposit flow parameters: {'amount': 60372418057498912008}
seq: 0 flow: 8 flow name: deposit flow parameters: {'amount': 33094638221113269924}
seq: 0 flow: 9 flow name: withdraw flow parameters: {'percent': 0.6947171593982429}
seq: 0 flow: 10 flow name: withdraw flow parameters: {'percent': 0.8114980558205607}
seq: 0 flow: 11 flow name: deposit flow parameters: {'amount': 78118069607095870035}
seq: 0 flow: 12 flow name: deposit flow parameters: {'amount': 62021121406117012385}
seq: 0 flow: 13 flow name: deposit flow parameters: {'amount': 199919492465328742484}
seq: 0 flow: 14 flow name: withdraw flow parameters: {'percent': 0.5432016870508934}
seq: 0 flow: 15 flow name: withdraw flow parameters: {'percent': 0.3566779610773797}
seq: 0 flow: 16 flow name: deposit flow parameters: {'amount': 149107258805448375293}
seq: 0 flow: 17 flow name: withdraw flow parameters: {'percent': 0.6758670853308426}
seq: 0 flow: 18 flow name: deposit flow parameters: {'amount': 186120250676001303782}
seq: 0 flow: 19 flow name: withdraw flow parameters: {'percent': 0.9210481989779773}
seq: 0 flow: 20 flow name: deposit flow parameters: {'amount': 200000000000000000000}
seq: 0 flow: 21 flow name: deposit flow parameters: {'amount': 35323240704015248515}
seq: 0 flow: 22 flow name: deposit flow parameters: {'amount': 56406145987655460847}
seq: 0 flow: 23 flow name: withdraw flow parameters: {'percent': 0.7510716681550472}
seq: 0 flow: 24 flow name: withdraw flow parameters: {'percent': 0.3299035247142814}
seq: 0 flow: 25 flow name: withdraw flow parameters: {'percent': 0.06541431906922635}
seq: 0 flow: 26 flow name: deposit flow parameters: {'amount': 46743786755147626526}
seq: 0 flow: 27 flow name: deposit flow parameters: {'amount': 69018581798447231015}
seq: 0 flow: 28 flow name: deposit flow parameters: {'amount': 95340694163613499668}
seq: 0 flow: 29 flow name: withdraw flow parameters: {'percent': 0.7706955830267418}
```
