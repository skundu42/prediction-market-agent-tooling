import time
from datetime import timedelta

import numpy as np
import pytest
from eth_typing import HexAddress, HexStr
from web3 import Web3

from prediction_market_agent_tooling.config import APIKeys
from prediction_market_agent_tooling.gtypes import xDai, xdai_type
from prediction_market_agent_tooling.loggers import logger
from prediction_market_agent_tooling.markets.data_models import Currency, TokenAmount
from prediction_market_agent_tooling.markets.omen.data_models import (
    OMEN_FALSE_OUTCOME,
    OMEN_TRUE_OUTCOME,
)
from prediction_market_agent_tooling.markets.omen.omen import (
    OMEN_DEFAULT_MARKET_FEE,
    OmenAgentMarket,
    binary_omen_buy_outcome_tx,
    omen_create_market_tx,
    omen_fund_market_tx,
    omen_redeem_full_position_tx,
    omen_remove_fund_market_tx,
    pick_binary_market,
)
from prediction_market_agent_tooling.markets.omen.omen_contracts import (
    OmenRealitioContract,
)
from prediction_market_agent_tooling.markets.omen.omen_subgraph_handler import (
    OmenSubgraphHandler,
)
from prediction_market_agent_tooling.tools.balances import get_balances
from prediction_market_agent_tooling.tools.utils import utcnow
from prediction_market_agent_tooling.tools.web3_utils import xdai_to_wei
from tests_integration.conftest import is_contract

DEFAULT_REASON = "Test logic need to be rewritten for usage of local chain, see ToDos"


@pytest.mark.skip(reason=DEFAULT_REASON)
def test_create_bet_withdraw_resolve_market(
    local_web3: Web3,
    test_keys: APIKeys,
) -> None:
    omen_subgraph_handler = OmenSubgraphHandler()
    wait_time = 60

    # Create a market with a very soon to be resolved question that will most probably be No.
    question = f"Will GNO be above $10000 in {wait_time} seconds from now?"
    closing_time = utcnow() + timedelta(seconds=wait_time)

    market_address = omen_create_market_tx(
        api_keys=test_keys,
        initial_funds=xdai_type(0.001),
        fee=OMEN_DEFAULT_MARKET_FEE,
        question=question,
        closing_time=closing_time,
        category="cryptocurrency",
        language="en",
        outcomes=[OMEN_TRUE_OUTCOME, OMEN_FALSE_OUTCOME],
        auto_deposit=True,
        web3=local_web3,
    )
    logger.debug(f"Market created at address: {market_address}")
    # ToDo - Fix call here (subgraph will not update on localchain). Retrieve data directly from contract.
    market = omen_subgraph_handler.get_omen_market_by_market_id(market_address)

    # Double check the market was created correctly.
    assert market.question_title == question

    # Bet on the false outcome.
    logger.debug("Betting on the false outcome.")
    agent_market = OmenAgentMarket.from_data_model(market)

    binary_omen_buy_outcome_tx(
        api_keys=test_keys,
        amount=xdai_type(0.001),
        market=agent_market,
        binary_outcome=False,
        auto_deposit=True,
    )

    # TODO: Add withdraw funds from the market.

    # Wait until the realitio question is opened (== market is closed).
    logger.debug("Waiting for the market to close.")
    time.sleep(wait_time)

    # Submit the answer and verify it was successfully submitted.
    logger.debug(f"Submitting the answer to {market.question.id=}.")

    OmenRealitioContract().submitAnswer(
        api_keys=test_keys,
        question_id=market.question.id,
        answer=OMEN_FALSE_OUTCOME,
        outcomes=market.question.outcomes,
        bond=xdai_to_wei(xDai(0.001)),
    )

    # ToDo - Instead of subgraph, fetch data directly from contract.
    answers = omen_subgraph_handler.get_answers(market.question.id)
    assert len(answers) == 1, answers
    assert answers[0].answer == OMEN_FALSE_OUTCOME, answers[0]

    # Note: We can not redeem the winning bet here, because the answer gets settled in 24 hours.
    # The same goes about claiming bonded xDai on Realitio.


def test_omen_create_market(
    local_web3: Web3,
    test_keys: APIKeys,
) -> None:
    market_address = omen_create_market_tx(
        api_keys=test_keys,
        initial_funds=xdai_type(0.001),
        question="Will GNO hit $1000 in 2 minutes from creation of this market?",
        closing_time=utcnow() + timedelta(minutes=2),
        category="cryptocurrency",
        language="en",
        outcomes=[OMEN_TRUE_OUTCOME, OMEN_FALSE_OUTCOME],
        auto_deposit=True,
        web3=local_web3,
    )

    assert is_contract(local_web3, market_address)


@pytest.mark.skip(reason=DEFAULT_REASON)
def test_omen_redeem_positions(
    local_web3: Web3,
    test_keys: APIKeys,
) -> None:
    # ToDo - create local chain with a given block B, where B is a block where a given agent had funds in the market.
    #  Then, create keys for that agent instead of relying on test_keys.
    market_id = (
        "0x6469da5478e5b2ddf9f6b7fba365e5670b7880f4".lower()
    )  # Market on which agent previously betted on
    subgraph_handler = OmenSubgraphHandler()
    market_data_model = subgraph_handler.get_omen_market_by_market_id(
        market_id=HexAddress(HexStr(market_id))
    )
    market = OmenAgentMarket.from_data_model(market_data_model)

    tx_receipt = omen_redeem_full_position_tx(
        api_keys=test_keys, market=market, web3=local_web3
    )

    assert tx_receipt


@pytest.mark.skip(reason=DEFAULT_REASON)
def test_create_market_fund_market_remove_funding() -> None:
    """
    ToDo - Once we have tests running in an isolated blockchain, write this test as follows:
        - Create a new market
        - Fund the market with amount
        - Assert balanceOf(creator) == amount
        - (Optionally) Close the market
        - Remove funding
        - Assert amount in xDAI is reflected in user's balance
    """
    assert False


def test_balance_for_user_in_market() -> None:
    user_address = Web3.to_checksum_address(
        "0x2DD9f5678484C1F59F97eD334725858b938B4102"
    )
    market_id = "0x59975b067b0716fef6f561e1e30e44f606b08803"
    market = OmenAgentMarket.get_binary_market(market_id)
    balance_yes: TokenAmount = market.get_token_balance(
        user_id=user_address,
        outcome=OMEN_TRUE_OUTCOME,
    )
    assert balance_yes.currency == Currency.xDai
    assert float(balance_yes.amount) == 0

    balance_no = market.get_token_balance(
        user_id=user_address,
        outcome=OMEN_FALSE_OUTCOME,
    )
    assert balance_no.currency == Currency.xDai
    assert float(balance_no.amount) == 0


def test_omen_fund_and_remove_fund_market(
    local_web3: Web3,
    test_keys: APIKeys,
) -> None:
    # You can double check your address at https://gnosisscan.io/ afterwards or at the market's address.
    market = OmenAgentMarket.from_data_model(pick_binary_market())
    logger.debug(
        "Fund and remove funding market test address:",
        market.market_maker_contract_address_checksummed,
    )

    funds = xdai_to_wei(xdai_type(0.1))
    remove_fund = xdai_to_wei(xdai_type(0.01))

    omen_fund_market_tx(
        api_keys=test_keys,
        market=market,
        funds=funds,
        auto_deposit=True,
        web3=local_web3,
    )

    omen_remove_fund_market_tx(
        api_keys=test_keys,
        market=market,
        shares=remove_fund,
        web3=local_web3,
    )


def test_omen_buy_and_sell_outcome(
    local_web3: Web3,
    test_keys: APIKeys,
) -> None:
    # Tests both buying and selling, so we are back at the square one in the wallet (minues fees).
    # You can double check your address at https://gnosisscan.io/ afterwards.
    market = OmenAgentMarket.from_data_model(pick_binary_market())
    outcome = True
    outcome_str = OMEN_TRUE_OUTCOME if outcome else OMEN_FALSE_OUTCOME
    bet_amount = market.get_bet_amount(amount=0.4)

    api_keys = APIKeys(BET_FROM_PRIVATE_KEY=test_keys.bet_from_private_key)

    def get_market_outcome_tokens(market: OmenAgentMarket, user_id: str) -> TokenAmount:
        return market.get_token_balance(user_id=user_id, outcome=outcome_str)

    # Check that we have no initial position in the market.
    assert (
        get_market_outcome_tokens(
            user_id=api_keys.bet_from_address,
            market=market,
        ).amount
        == 0
    )

    # Check our wallet has sufficient funds
    balances = get_balances(api_keys.bet_from_address)
    assert balances.xdai + balances.wxdai > bet_amount.amount

    market.place_bet(outcome=outcome, amount=bet_amount, web3=local_web3)

    # Check that we now have a position in the market.
    outcome_tokens = get_market_outcome_tokens(market, api_keys.bet_from_address)
    assert outcome_tokens.amount > 0

    market.sell_tokens(outcome=outcome, amount=outcome_tokens, web3=local_web3)
    remaining_tokens = get_market_outcome_tokens(market, api_keys.bet_from_address)

    # Check that we have sold our entire stake in the market.
    assert np.isclose(remaining_tokens.amount, 0)
