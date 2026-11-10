// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Single-asset, buyer-authorized ERC20 escrow. Not audited or mainnet approved.
interface IERC20Sovereign {
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 value) external returns (bool);
    function transferFrom(address from, address to, uint256 value) external returns (bool);
}
contract SovereignEscrow {
    enum State { None, Funded, Released, Refunded }
    struct Order {
        address payer;
        address provider;
        uint128 amount;
        uint64 expires;
        State state;
        bytes32 commitment;
    }
    IERC20Sovereign public immutable token;
    mapping(bytes32 => Order) public orders;
    uint256 private gate = 1;
    event Funded(bytes32 indexed orderId, address indexed payer, address indexed provider, uint256 amount, uint64 expires, bytes32 commitment);
    event Released(bytes32 indexed orderId, uint256 amount);
    event Refunded(bytes32 indexed orderId, uint256 amount);
    error Invalid();
    error Unauthorized();
    error NotReady();
    error TokenFailure();
    error Reentered();
    modifier nonReentrant() {
        if (gate != 1) revert Reentered();
        gate = 2;
        _;
        gate = 1;
    }
    constructor(address token_) {
        if (token_ == address(0) || token_.code.length == 0) revert Invalid();
        token = IERC20Sovereign(token_);
    }
    function fund(bytes32 orderId, address provider, uint128 amount, uint64 expires, bytes32 commitment)
        external nonReentrant
    {
        if (orderId == bytes32(0) || commitment == bytes32(0) || amount == 0 ||
            provider == address(0) || provider == msg.sender ||
            expires <= block.timestamp + 1 hours || expires > block.timestamp + 30 days ||
            orders[orderId].state != State.None) revert Invalid();
        uint256 beforeBal = token.balanceOf(address(this));
        _callOptional(abi.encodeCall(IERC20Sovereign.transferFrom, (msg.sender, address(this), uint256(amount))));
        uint256 afterBal = token.balanceOf(address(this));
        if (afterBal < beforeBal || afterBal - beforeBal != amount) revert TokenFailure();
        orders[orderId] = Order(msg.sender, provider, amount, expires, State.Funded, commitment);
        emit Funded(orderId, msg.sender, provider, amount, expires, commitment);
    }
    /// @dev Evidence hash is buyer-supplied. It is NOT a cryptographic proof that service was delivered.
    function release(bytes32 orderId, bytes32 evidenceHash) external nonReentrant {
        Order storage order = orders[orderId];
        if (order.state != State.Funded) revert NotReady();
        if (msg.sender != order.payer) revert Unauthorized();
        if (evidenceHash != order.commitment) revert Invalid();
        order.state = State.Released;
        _callOptional(abi.encodeCall(IERC20Sovereign.transfer, (order.provider, uint256(order.amount))));
        emit Released(orderId, order.amount);
    }
    function refund(bytes32 orderId) external nonReentrant {
        Order storage order = orders[orderId];
        if (order.state != State.Funded) revert NotReady();
        if (msg.sender != order.payer) revert Unauthorized();
        if (block.timestamp < order.expires) revert NotReady();
        order.state = State.Refunded;
        _callOptional(abi.encodeCall(IERC20Sovereign.transfer, (order.payer, uint256(order.amount))));
        emit Refunded(orderId, order.amount);
    }
    function _callOptional(bytes memory data) internal {
        (bool success, bytes memory returndata) = address(token).call(data);
        if (!success || (returndata.length != 0 && (returndata.length != 32 || !abi.decode(returndata, (bool)))))
            revert TokenFailure();
    }
}
