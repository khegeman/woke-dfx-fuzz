// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.15;

import "woke/console.sol";
import "protocol-v2/src/lib/ABDKMath64x64.sol";

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