import asyncio
from agent import detect_intent, process_message

SEP = "=" * 55

MESSAGES = [
    "I just bought EURUSD at 1.0850, stop at 1.0800, target 1.0950",
    "What's the price of gold?",
    "How much should I trade if I buy GBPUSD at 1.2700 with sl at 1.2650?",
    "Show me my open trades",
    "How did I do this week?",
    "What's moving the market today?",
    "What is a pip?",
    "Change my balance to 75",
]

async def main():
    for i, msg in enumerate(MESSAGES, 1):
        print(f"\nTEST {i}: \"{msg}\"")
        print(SEP)
        intent_result = await detect_intent(msg)
        print(f"Intent: {intent_result.get('intent')} (confidence: {intent_result.get('confidence')})")
        print()
        response = await process_message(msg)
        print(response)

asyncio.run(main())
