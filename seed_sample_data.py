#!/usr/bin/env python3
"""Seed database with sample ICT quotes from multiple documents for dashboard preview."""

from datetime import datetime, timedelta, timezone
from core.models import Quote, Post, PostStatus, init_db, get_session

UTC = timezone.utc

SAMPLE_QUOTES = [
    # === Beauty for Ashes (April 14, 2023) ===
    {
        "content": "The markets are not a toy store. It is not a place where you can be a kid. It is war.",
        "source": "Beauty for Ashes",
        "topic": "Trading Psychology",
        "quality_score": 9.2,
    },
    {
        "content": "You have to have rules. If you do not recognize that, you will end up in a gambler's cycle.",
        "source": "Beauty for Ashes",
        "topic": "Discipline",
        "quality_score": 9.0,
    },
    {
        "content": "If your relationships and the way you conduct yourself outside of trading are flawed, it will be magnified in trading.",
        "source": "Beauty for Ashes",
        "topic": "Trading Psychology",
        "quality_score": 8.7,
    },
    {
        "content": "Everyone that goes outside of the plan, the approach, the playbook—the results are random.",
        "source": "Beauty for Ashes",
        "topic": "Model Following",
        "quality_score": 8.5,
    },
    {
        "content": "Nobody has time to learn anything properly. You are doing what everybody else has done—pushed buttons, found out.",
        "source": "Beauty for Ashes",
        "topic": "Self-Improvement",
        "quality_score": 8.3,
    },

    # === When Being Right Is No Longer Enough (March 18, 2023) ===
    {
        "content": "Being right and being profitable are not the same. You can call direction and still lose through timing errors or hesitation.",
        "source": "When Being Right Is No Longer Enough",
        "topic": "Trading Psychology",
        "quality_score": 9.4,
    },
    {
        "content": "The key shift is losing the need to be right. When being right happens as a byproduct of process—not as your target—you're nearing readiness.",
        "source": "When Being Right Is No Longer Enough",
        "topic": "Discipline",
        "quality_score": 9.3,
    },
    {
        "content": "Your aim isn't fortune-telling—it's consistency. Do the measured, studied things that historically tilt probability your way.",
        "source": "When Being Right Is No Longer Enough",
        "topic": "Model Following",
        "quality_score": 9.1,
    },
    {
        "content": "Each position is a single experiment: you define where price should go, where you're wrong, and you accept the result.",
        "source": "When Being Right Is No Longer Enough",
        "topic": "Risk Management",
        "quality_score": 8.9,
    },
    {
        "content": "When a trade puts you in troubled waters and anxiety kicks in, reduce risk immediately. Doing so breaks the need to be right.",
        "source": "When Being Right Is No Longer Enough",
        "topic": "Risk Management",
        "quality_score": 8.8,
    },
    {
        "content": "Trading must feel routine. The path to that state is desensitizing yourself to outcomes and making everything about execution.",
        "source": "When Being Right Is No Longer Enough",
        "topic": "Discipline",
        "quality_score": 8.7,
    },
    {
        "content": "The progression is non-negotiable: backtesting, studying past moves, tape reading, then demo execution. Each phase demands patience.",
        "source": "When Being Right Is No Longer Enough",
        "topic": "Self-Improvement",
        "quality_score": 8.6,
    },
    {
        "content": "You don't need to be right; you need to follow a sound model. Results should be detached from emotion.",
        "source": "When Being Right Is No Longer Enough",
        "topic": "Trading Psychology",
        "quality_score": 8.5,
    },
    {
        "content": "Guard your mind and preserve your clarity. Once you've desensitized yourself to outcomes, your pursuit isn't being right—it's following your model.",
        "source": "When Being Right Is No Longer Enough",
        "topic": "Trading Psychology",
        "quality_score": 8.4,
    },

    # === Through The Looking Glass (Feb 26, 2023) ===
    {
        "content": "You must remain indifferent to the outcome. Sometimes a trade will be profitable, other times it won't.",
        "source": "Through The Looking Glass",
        "topic": "Trading Psychology",
        "quality_score": 9.0,
    },
    {
        "content": "One of the best things that can happen is losing an account. It forces you to respect risk.",
        "source": "Through The Looking Glass",
        "topic": "Risk Management",
        "quality_score": 8.9,
    },
    {
        "content": "Professional gamblers are not impulsive gamblers. They're calculated money managers. They embrace uncertainty.",
        "source": "Through The Looking Glass",
        "topic": "Risk Management",
        "quality_score": 8.8,
    },
    {
        "content": "Entry patterns are numerous. There are many ways to get into a move, but only one side of the narrative is going to develop.",
        "source": "Through The Looking Glass",
        "topic": "Market Structure",
        "quality_score": 8.7,
    },
    {
        "content": "You have to predict price. That's exactly what we're doing. That's like telling a football team their job is not to score touchdowns.",
        "source": "Through The Looking Glass",
        "topic": "Market Structure",
        "quality_score": 8.6,
    },
    {
        "content": "Nobody has ever started this industry, gotten it all right from day one, and never had hardships. Everyone comes in here tied to the fire.",
        "source": "Through The Looking Glass",
        "topic": "Self-Improvement",
        "quality_score": 8.5,
    },
    {
        "content": "If you blow an account and don't respect the risk, you'll just do the same thing with the next one.",
        "source": "Through The Looking Glass",
        "topic": "Risk Management",
        "quality_score": 8.4,
    },
    {
        "content": "You'll discover things about yourself that you don't like. You're going to act impulsively because you're not disciplined.",
        "source": "Through The Looking Glass",
        "topic": "Self-Improvement",
        "quality_score": 8.3,
    },

    # === Unfolding Truths (March 23, 2023) ===
    {
        "content": "You're often the one adding complexity. I teach many tools, but I'm not saying they apply at all times, on all timeframes, or across every asset.",
        "source": "Unfolding Truths",
        "topic": "Model Following",
        "quality_score": 8.9,
    },
    {
        "content": "Price seeks liquidity above old highs and below old lows. When it isn't doing that, it's reaching into premium to reprice an inefficiency.",
        "source": "Unfolding Truths",
        "topic": "Market Structure",
        "quality_score": 9.1,
    },
    {
        "content": "You commit to a process that keeps you calm, not anxious. You wait for the market to present the opportunity. You don't react; you anticipate.",
        "source": "Unfolding Truths",
        "topic": "Patience",
        "quality_score": 9.0,
    },
    {
        "content": "You can make 20 handles in a day even when the market isn't trending—chop just means you assemble them over time.",
        "source": "Unfolding Truths",
        "topic": "Edge Tracking",
        "quality_score": 8.7,
    },
    {
        "content": "Think like a hunter. Set up in advance, wait for your window, and take the five handles when the conditions align.",
        "source": "Unfolding Truths",
        "topic": "Patience",
        "quality_score": 8.8,
    },
    {
        "content": "Don't see me as your educator—see me as your best friend in the market, the voice of reason keeping you on track.",
        "source": "Unfolding Truths",
        "topic": "Self-Improvement",
        "quality_score": 8.2,
    },
    {
        "content": "If you're competing with anyone but yourself, you're doing it wrong. That guarantees performance anxiety, regret, and remorse.",
        "source": "Unfolding Truths",
        "topic": "Trading Psychology",
        "quality_score": 8.6,
    },

    # === Until The Brakes Fall Off (March 26, 2023) ===
    {
        "content": "Everybody comes into trading with a weak mindset. You're impatient. You want to rush into making money.",
        "source": "Until The Brakes Fall Off",
        "topic": "Trading Psychology",
        "quality_score": 8.8,
    },
    {
        "content": "You slip into drawdown. At first, losing just what you made that day is tolerable. But when you start eating into what you built over a week, that really hurts.",
        "source": "Until The Brakes Fall Off",
        "topic": "Risk Management",
        "quality_score": 8.7,
    },
    {
        "content": "As soon as you start feeling emotional, like you have to take the trade, that's your clear signal to turn the charts off and walk away.",
        "source": "Until The Brakes Fall Off",
        "topic": "Discipline",
        "quality_score": 9.2,
    },
    {
        "content": "You've got adrenaline pouring through your body. Those chemicals are telling you that you've turned this into an emergency. You're lying to yourself.",
        "source": "Until The Brakes Fall Off",
        "topic": "Trading Psychology",
        "quality_score": 8.9,
    },
    {
        "content": "Close all positions. Remove all pending orders. Turn the charts off. Walk away. That's it. It's handled. No more emergency.",
        "source": "Until The Brakes Fall Off",
        "topic": "Discipline",
        "quality_score": 9.0,
    },
    {
        "content": "How did you get to your equity high the first time? Incremental, modular steps. Basic, boring execution. Following your rules.",
        "source": "Until The Brakes Fall Off",
        "topic": "Model Following",
        "quality_score": 8.8,
    },
    {
        "content": "Before the drawdown, you weren't trying to do crazy stuff. You were just focused on: find the next setup, take the trade, take the profit, be done.",
        "source": "Until The Brakes Fall Off",
        "topic": "Discipline",
        "quality_score": 8.6,
    },
    {
        "content": "That's how a normal drawdown becomes a blown account—not understanding how fragile your mentality has become.",
        "source": "Until The Brakes Fall Off",
        "topic": "Trading Psychology",
        "quality_score": 8.5,
    },
]


def seed_quotes():
    init_db()
    session = get_session()

    session.query(Quote).delete()
    session.commit()

    for quote_data in SAMPLE_QUOTES:
        quote = Quote(
            content=quote_data["content"],
            source=quote_data["source"],
            topic=quote_data["topic"],
            quality_score=quote_data["quality_score"],
            approved=True,
            created_at=datetime.now(UTC)
        )
        session.add(quote)

    session.commit()
    print(f"Seeded {len(SAMPLE_QUOTES)} quotes from 5 documents")
    return len(SAMPLE_QUOTES)


def seed_posts():
    session = get_session()

    session.query(Post).delete()
    session.commit()

    from core.post_planner import PostPlanner, build_quote_post_text
    planner = PostPlanner()

    quotes = planner.get_shuffled_quotes(14, min_score=7.0)

    base_time = datetime.now(UTC).replace(hour=9, minute=0, second=0, microsecond=0)
    if base_time < datetime.now(UTC):
        base_time += timedelta(days=1)

    for i, quote in enumerate(quotes):
        scheduled = base_time + timedelta(days=i)
        content = build_quote_post_text(quote.content, supporting_text=quote.topic or "")

        post = Post(
            quote_id=quote.id,
            platform="twitter",
            content=content,
            scheduled_time=scheduled,
            status=PostStatus.APPROVED.value if i < 3 else PostStatus.PENDING.value,
            created_at=datetime.now(UTC)
        )
        session.add(post)

    session.commit()
    print(f"Seeded {len(quotes)} shuffled posts from multiple sources")
    return len(quotes)


if __name__ == "__main__":
    seed_quotes()
    seed_posts()
