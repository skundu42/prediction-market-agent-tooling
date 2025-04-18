import pytest
from ape import accounts as ape_accounts
from ape_test import TestAccount
from eth_typing import ChecksumAddress
from web3 import Web3

from prediction_market_agent_tooling.config import APIKeys
from prediction_market_agent_tooling.gtypes import private_key_type, xdai_type
from prediction_market_agent_tooling.tools.balances import get_balances
from prediction_market_agent_tooling.tools.contract import SimpleTreasuryContract
from prediction_market_agent_tooling.tools.web3_utils import send_xdai_to, xdai_to_wei
from tests_integration_with_local_chain.conftest import (
    execute_tx_from_impersonated_account,
)


@pytest.fixture
def labs_deployer() -> ChecksumAddress:
    return Web3.to_checksum_address("0x32aABa58DE76BdbA912FC14Fcc11b8Aa6227aeE9")


@pytest.fixture(scope="function")
def simple_treasury_contract() -> SimpleTreasuryContract:
    return SimpleTreasuryContract()


def test_required_nft_balance(
    local_web3: Web3, simple_treasury_contract: SimpleTreasuryContract
) -> None:
    initial_required_nft_balance = simple_treasury_contract.required_nft_balance(
        web3=local_web3
    )
    # Initial value after deployment is 3
    assert initial_required_nft_balance == 3


def test_owner(
    local_web3: Web3,
    labs_deployer: ChecksumAddress,
    simple_treasury_contract: SimpleTreasuryContract,
) -> None:
    owner = simple_treasury_contract.owner(web3=local_web3)
    assert owner == labs_deployer


def test_withdraw(
    local_web3: Web3,
    accounts: list[TestAccount],
    labs_deployer: ChecksumAddress,
    simple_treasury_contract: SimpleTreasuryContract,
) -> None:
    executor = accounts[0]
    amount_transferred = xdai_type(5)
    # Transfer all the balance to the treasury
    send_xdai_to(
        web3=local_web3,
        from_private_key=private_key_type(executor.private_key),
        to_address=simple_treasury_contract.address,
        value=xdai_to_wei(amount_transferred),
    )
    owner = simple_treasury_contract.owner(web3=local_web3)
    # Set required
    with ape_accounts.use_sender(owner) as s:
        execute_tx_from_impersonated_account(
            web3=local_web3,
            impersonated_account=s,
            contract_address=simple_treasury_contract.address,
            contract_abi=simple_treasury_contract.abi,
            function_name="setRequiredNFTBalance",
            function_params=[0],
        )

    # call withdraw
    keys = APIKeys(
        BET_FROM_PRIVATE_KEY=private_key_type(executor.private_key), SAFE_ADDRESS=None
    )
    simple_treasury_contract.withdraw(api_keys=keys, web3=local_web3)

    # Assert treasury is empty
    final_treasury_balance = get_balances(
        simple_treasury_contract.address, web3=local_web3
    ).xdai
    assert int(final_treasury_balance) == 0
