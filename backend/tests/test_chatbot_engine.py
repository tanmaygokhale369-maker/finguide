from app.ai.chatbot.rule_based import RuleBasedChatbotEngine


def test_greeting_gets_a_greeting_reply():
    engine = RuleBasedChatbotEngine()
    reply = engine.generate_reply(history=[], user_message="Hello there")
    assert "FinGuide+" in reply.content


def test_help_request_states_current_capabilities_honestly():
    engine = RuleBasedChatbotEngine()
    reply = engine.generate_reply(history=[], user_message="what can you do?")
    assert "can't yet" in reply.content or "not yet" in reply.content.lower()


def test_thanks_gets_acknowledged():
    engine = RuleBasedChatbotEngine()
    reply = engine.generate_reply(history=[], user_message="thanks a lot")
    assert "welcome" in reply.content.lower()


def test_farewell_gets_a_goodbye():
    engine = RuleBasedChatbotEngine()
    reply = engine.generate_reply(history=[], user_message="bye")
    assert "goodbye" in reply.content.lower() or "bye" in reply.content.lower()


def test_unrecognized_input_gets_the_honest_fallback():
    engine = RuleBasedChatbotEngine()
    reply = engine.generate_reply(history=[], user_message="asdkjfh qwoeiruqwoe")
    assert "rule-based" in reply.content.lower()


def test_engine_never_states_a_specific_number_or_recommendation():
    """
    Cheap but meaningful regression guard: the rule-based engine must
    never fabricate a financial figure or give advice, per the
    ChatbotEngine interface contract. This checks canned replies don't
    contain digits (a crude but effective proxy for "no fabricated
    numbers") across every branch.
    """
    engine = RuleBasedChatbotEngine()
    for message in ["hi", "help", "thanks", "bye", "gibberish"]:
        reply = engine.generate_reply(history=[], user_message=message)
        assert not any(char.isdigit() for char in reply.content)
