import asyncio
import sys
sys.path.insert(0, "D:/Sreekanta/VS Code Project/Desktop AI/AuraAI")
from core.aura_core import AuraCore

async def main():
    core = AuraCore.get_instance()
    
    # Let's bypass actual STT/TTS and just send text directly through the request pipeline
    print("\n=== TURN 1 ===")
    t1 = "current dollar to rupees conversion rate"
    print(f"You > {t1}")
    res1 = await core.process_request(t1)
    print(f"Aura > {res1}")
    
    print("\n=== TURN 2 ===")
    t2 = "as of today?"
    print(f"You > {t2}")
    res2 = await core.process_request(t2)
    print(f"Aura > {res2}")
    
    print("\n=== TURN 3 ===")
    t3 = "as of today whats the convertion rate of doller to inr"
    print(f"You > {t3}")
    res3 = await core.process_request(t3)
    print(f"Aura > {res3}")
    
    print("\n=== BOUNDARY TESTS ===")
    boundaries = [
        "what time is it?",
        "what is today's date?",
        "what is the current time in London?",
        "what is today's USD to INR exchange rate?",
        "as of today, what's the USD to INR exchange rate?",
    ]
    
    for q in boundaries:
        print(f"\nYou > {q}")
        res = await core.process_request(q)
        print(f"Aura > {res}")

if __name__ == "__main__":
    asyncio.run(main())
