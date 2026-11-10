// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
contract MockToken {
    string public constant name="Local Test Token";
    string public constant symbol="LTT";
    uint8 public constant decimals=6;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    function mint(address to, uint256 value) external { balanceOf[to] += value; }
    function approve(address spender, uint256 value) external returns (bool) {allowance[msg.sender][spender]=value;return true;}
    function transfer(address to, uint256 value) external returns (bool) {
        require(balanceOf[msg.sender]>=value,"BALANCE");
        balanceOf[msg.sender]-=value; balanceOf[to]+=value;return true;
    }
    function transferFrom(address from,address to,uint256 value) external returns(bool) {
        require(allowance[from][msg.sender]>=value && balanceOf[from]>=value,"ALLOWANCE_OR_BALANCE");
        allowance[from][msg.sender]-=value;balanceOf[from]-=value;balanceOf[to]+=value;return true;
    }
}
