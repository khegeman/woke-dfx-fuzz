# Overview

This repository contains fuzz tests written in Woke that accompany the article [Invariant Validation through Fuzz Testing: A Case Study on DFX Finance](https://dev.to/khegeman/invariant-validation-through-fuzz-testing-a-case-study-on-dfx-finance-2lf0)

# Install

clone the repository 

```
git clone --recursive --depth 1 git@github.com:khegeman/woke-dfx-fuzz.git
```

Then create a virtual environment.  One way to do this is with conda

```
conda create --name woke-dfx python=3.10.11
conda activate woke-dfx
```

Install the Python dependencies

```
pip install -r requirements.txt
```

Compile Solidity contracts for DFX and generate Python classes

```
woke init pytypes
```

# Configure

Create a .env file that will hold the environment variables for an RPC for the corresponding network.  This should point to an RPC url for Polygon at a site like [Alchemy](https://www.alchemy.com).  

```
POL_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/XXXXXXXXXXXXXXXXXXXXXXXXXXXXX
ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

# Running

There are 3 tests in the repository.  

## Polygon network, before the vulnerability was fixed

```
 woke test tests/test_polygon.py 
```

Running this test will fail with an assertion. 

```
    @invariant(period=1)
    def utility(self) -> None:
        """Check and update the utility invariant

        This function asserts that the invariant (as calculated by _calcInvariant)
        has not decreased. This is to ensure that "utility" in the pool is not decreasing.

        Raises:
            AssertionError: If the invariant has decreased.
        """
        inv = self._calcInvariant()
>       assert inv >= self._previous_inv, "utility decreased."
E       AssertionError: utility decreased.
```

## Polygon network, after the vulnerability was fixed

This test should pass.

```
 woke test tests/test_fix.py 
```

## Ethereum

The test can also be run on Eth mainnet.  This changes the pool and token addresses accordingly.  

This test should pass.

```
 woke test tests/test_eth.py 
```
