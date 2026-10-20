from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ToolbenchWebToolkit:
    """Fixed-fixture web toolkit for mock web search and page fetching.

    This toolkit provides deterministic web operations using a fixed corpus
    of pages. It supports:
    - search_pages: Keyword search over fixture pages
    - fetch_page: Retrieve full page content by URL
    - list_topics: List available topics
    - create_research_note: Create research note (state mutation)
    - get_research_note: Retrieve created note

    No real network access. All data from local fixture.
    """

    # Default fixture: 12 web pages covering useful topics
    DEFAULT_PAGES: List[Dict[str, Any]] = [
        {
            "url": "https://community.example.org/local-food-banks",
            "title": "Local Food Banks and Pantries — Community Resources Guide",
            "topic": "local_community",
            "source": "Community Action Network",
            "published_date": "2025-11-15",
            "reading_level": "easy",
            "tags": ["food", "community", "assistance", "local"],
            "snippet": "Guide to local food banks, pantries, and meal programs. Includes eligibility, hours, and locations.",
            "text": """# Local Food Banks and Pantries

Finding food assistance in your community.

## Main Food Bank Locations

| Location | Hours | Eligibility |
|----------|-------|-------------|
| Downtown Community Center | Mon-Fri 9am-5pm | Open to all |
| North Side Church Pantry | Tue, Thu 10am-2pm | ID required |
| South District Hub | Sat 8am-12pm | No restrictions |

## What to Bring

- Photo ID (optional at some locations)
- Proof of address (utility bill)
- Family size information

## Additional Programs

- Weekend Backpack Program for families with children
- Senior Meal Delivery (60+ only)
- Emergency 3-day supply (walk-in available)

Contact: foodhelp@community.example.org
""",
        },
        {
            "url": "https://transit.example.gov/routes-and-schedules",
            "title": "Public Transit Routes and Schedules — Metro Transit Authority",
            "topic": "public_transit",
            "source": "Metro Transit Authority",
            "published_date": "2026-01-20",
            "reading_level": "medium",
            "tags": ["transit", "commuting", "schedules", "public"],
            "snippet": "Official transit authority guide covering bus routes, train lines, schedules, and fare information.",
            "text": """# Public Transit Routes and Schedules

Metro Transit Authority — Updated January 2026

## Bus Routes

| Route | Key Stops | Frequency |
|-------|-----------|-----------|
| Route 12 | Downtown → University → Mall | Every 15 min |
| Route 45 | Airport → Business Park → Terminal | Every 20 min |
| Route 78 | Residential Zone → City Center | Every 30 min |

## Train Lines

- **Blue Line**: North Terminal ↔ South Station (8am-10pm)
- **Green Line**: East Loop ↔ West Hub (6am-11pm)
- **Red Line**: Airport Express (24hr service)

## Fares

| Type | Price |
|------|-------|
| Single Ride | $2.50 |
| Day Pass | $8.00 |
| Monthly Pass | $95 |
| Senior/Student | $1.75 |

## Accessibility

All buses and trains wheelchair accessible. Priority seating available.

Contact: transit-info@example.gov
""",
        },
        {
            "url": "https://finance.example.org/budget-guide-2026",
            "title": "Personal Budgeting Guide 2026 — Consumer Finance Council",
            "topic": "budgeting",
            "source": "Consumer Finance Council",
            "published_date": "2026-02-01",
            "reading_level": "medium",
            "tags": ["budgeting", "finance", "money", "planning"],
            "snippet": "Step-by-step guide to creating a personal budget. Includes templates, tips, and common pitfalls.",
            "text": """# Personal Budgeting Guide 2026

Consumer Finance Council — Practical Money Management

## The 50/30/20 Rule

A simple budget framework:
- 50% for needs (housing, utilities, food, transport)
- 30% for wants (entertainment, dining, hobbies)
- 20% for savings and debt repayment

## Creating Your Budget

### Step 1: Track Spending
Review bank statements for 2-3 months to understand current spending patterns.

### Step 2: Set Categories
- Fixed expenses (rent, insurance)
- Variable expenses (groceries, utilities)
- Discretionary (entertainment, shopping)

### Step 3: Set Limits
Be realistic. If groceries are currently $400/month, setting $200 is unlikely to work.

### Step 4: Monitor Weekly
Check progress weekly, not monthly. Small adjustments early prevent overspending.

## Common Pitfalls

1. **Forgetting irregular expenses**: Gifts, car repairs, annual subscriptions
2. **No buffer**: Unexpected costs derail the budget
3. **Too rigid**: Budget should adapt, not punish

Download template: budget-template.xlsx
""",
        },
        {
            "url": "https://health.example.gov/flu-prevention-guide",
            "title": "Flu Prevention Guide — Public Health Department",
            "topic": "health_wellness",
            "source": "Public Health Department",
            "published_date": "2025-10-15",
            "reading_level": "easy",
            "tags": ["health", "flu", "prevention", "public"],
            "snippet": "Official health department guide on flu prevention, symptoms, and vaccination.",
            "text": """# Flu Prevention Guide

Public Health Department — Seasonal Health Information

## Getting Vaccinated

Flu vaccines are available at:
- Pharmacies (walk-in)
- Community clinics
- Doctor offices
- Workplace wellness programs (check with HR)

**Best time**: September to November, before flu season peaks.

## Daily Prevention

1. Wash hands frequently (20+ seconds with soap)
2. Avoid touching face (eyes, nose, mouth)
3. Cover coughs and sneezes
4. Stay home when sick
5. Clean shared surfaces (doorknobs, phones)

## Symptoms to Watch

- Fever (100°F+)
- Body aches
- Fatigue
- Cough, sore throat
- Runny nose

**When to seek care**: If symptoms worsen after 3-4 days, or difficulty breathing.

## High-Risk Groups

- Children under 5
- Adults 65+
- Pregnant individuals
- Chronic conditions (asthma, diabetes, heart disease)

Resources: health.example.gov/vaccine-locations
""",
        },
        {
            "url": "https://education.example.org/free-online-courses",
            "title": "Free Online Learning Resources — Education Access Initiative",
            "topic": "education",
            "source": "Education Access Initiative",
            "published_date": "2026-03-10",
            "reading_level": "medium",
            "tags": ["education", "learning", "online", "free"],
            "snippet": "Directory of free online courses and learning platforms. Covers coding, languages, professional skills.",
            "text": """# Free Online Learning Resources

Education Access Initiative — Open Learning for Everyone

## Coding and Technology

| Platform | Focus | Certificates |
|----------|-------|--------------|
| freeCodeCamp | Web dev, Python, JS | Free certificates |
| Codecademy Free Tier | Basic coding | No |
| Khan Academy | CS fundamentals | No |
| MIT OpenCourseWare | University-level | No |

## Languages

- **Duolingo**: Gamified learning, 40+ languages
- **Memrise**: Vocabulary-focused, community courses
- **BBC Languages**: Audio and video lessons

## Professional Skills

- **Coursera Free Courses**: Audit option for many courses
- **LinkedIn Learning**: Free trial, then paid
- **Google Career Certificates**: Financial aid available

## High School and College Prep

- Khan Academy: Full K-12 curriculum
- OpenStax: Free textbooks (college level)
- Crash Course: Engaging video series

## Tips for Success

1. Set specific goals (e.g., "finish 1 chapter per week")
2. Schedule regular time blocks
3. Join community forums for accountability
4. Track progress visually

Contact: learning@education.example.org
""",
        },
        {
            "url": "https://entertainment.example.local/movie-guide-family",
            "title": "Family Movie Guide — Weekend Entertainment",
            "topic": "entertainment",
            "source": "Weekend Entertainment Magazine",
            "published_date": "2026-04-25",
            "reading_level": "easy",
            "tags": ["movies", "entertainment", "family", "weekend"],
            "snippet": "Curated guide to family-friendly movies currently available. Age ratings and brief reviews.",
            "text": """# Family Movie Guide

Weekend Entertainment Magazine — April 2026 Edition

## Top Picks for Ages 5-12

| Title | Rating | Genre | Runtime |
|-------|--------|-------|---------|
| The Forest Adventure | PG | Animated adventure | 98 min |
| Space Pals | PG | Sci-fi comedy | 105 min |
| Magic Kingdom | PG | Fantasy | 112 min |

## Family Classics (Available on streaming)

1. **Finding Nemo** (PG) — Ocean adventure, great for all ages
2. **The Incredibles** (PG) — Superhero family fun
3. **Toy Story** series (G/PG) — Beloved for generations

## For Teens (13+)

- **Quest for Tomorrow** (PG-13) — Sci-fi adventure, mild action
- **High School Musical** (PG) — Fun, no concerns

## What to Avoid

- R-rated films for family movie night
- Horror/thriller for young children
- Films with excessive violence or language

## Planning Tips

- Check Common Sense Media for detailed reviews
- Runtime matters: <100 min for younger kids
- Have snacks ready before starting
- Discuss the movie afterward

Reviews: entertainment.example.local/reviews
""",
        },
        {
            "url": "https://privacy.example.org/digital-safety-guide",
            "title": "Digital Privacy and Safety Guide — Privacy Foundation",
            "topic": "privacy_digital_safety",
            "source": "Privacy Foundation",
            "published_date": "2026-01-05",
            "reading_level": "medium",
            "tags": ["privacy", "digital", "security", "online"],
            "snippet": "Practical guide to protecting privacy online. Covers passwords, social media, data sharing.",
            "text": """# Digital Privacy and Safety Guide

Privacy Foundation — Protecting Your Digital Life

## Password Best Practices

1. **Use unique passwords**: Never reuse across accounts
2. **Length matters**: 12+ characters recommended
3. **Consider passphrase**: "correct-horse-battery-staple" style
4. **Use password manager**: Bitwarden, 1Password, or built-in

## Social Media Privacy

| Platform | Key Settings |
|----------|--------------|
| Facebook | Privacy Checkup tool, limit "Friends of Friends" |
| Instagram | Private account option, story controls |
| Twitter/X | Protect tweets option, mute/block tools |

## Data Sharing Awareness

- **Email**: Unsubscribe from unused newsletters
- **Apps**: Review permissions (location, contacts, camera)
- **Shopping**: Opt out of data sharing at checkout
- **Search**: Use private browsing or DuckDuckGo

## Phishing Recognition

Warning signs:
- Urgent language ("act now!")
- Sender address mismatches official domain
- Suspicious links (hover to check)
- Requests for passwords or payment info

**Rule**: If unsure, don't click. Contact official source directly.

## Family Considerations

- Discuss privacy with children
- Set boundaries for photo sharing
- Review gaming platform privacy settings

Resources: privacy.example.org/tools
""",
        },
        {
            "url": "https://accessibility.example.gov/family-transport-guide",
            "title": "Accessible Family Transportation Guide — Accessibility Office",
            "topic": "accessibility_family",
            "source": "City Accessibility Office",
            "published_date": "2026-02-28",
            "reading_level": "medium",
            "tags": ["accessibility", "family", "transport", "disability"],
            "snippet": "Guide to accessible transportation options for families with disabilities or mobility needs.",
            "text": """# Accessible Family Transportation Guide

City Accessibility Office — Options for Every Family

## Paratransit Services

Door-to-door service for those who cannot use regular transit.

**Eligibility**: Disability that prevents regular transit use
**Booking**: Call 24 hours ahead or use app
**Cost**: Same as regular transit fare

## Vehicle Accommodations

- Wheelchair-accessible vehicles: All transit buses
- Priority seating: Front of bus/train
- Audio announcements: Route and stop info
- Visual displays: LED screens at stations

## Family-Specific Options

### Stroller Accommodations
- Designated stroller areas on buses
- Fold strollers on crowded vehicles
- Some trains have family car

### Traveling with Medical Equipment
- Oxygen tanks permitted
- Notify driver of mobility aids
- Service animals always welcome

## Parking Programs

- Disabled parking placards: Apply through DMV
- Temporary placards: Available for short-term needs
- Accessible parking enforcement: Report violations

## Planning Tips

- Download transit app for real-time updates
- Test routes before important appointments
- Identify backup options
- Carry accessibility documentation

Contact: access@example.gov | Phone: (555) 123-4567
""",
        },
        {
            "url": "https://community.example.org/volunteer-opportunities",
            "title": "Volunteer Opportunities Directory — Community Action Network",
            "topic": "local_community",
            "source": "Community Action Network",
            "published_date": "2025-09-20",
            "reading_level": "easy",
            "tags": ["volunteer", "community", "service", "local"],
            "snippet": "Directory of local volunteer opportunities. Covers food banks, tutoring, environmental, elderly support.",
            "text": """# Volunteer Opportunities Directory

Community Action Network — Ways to Help

## Ongoing Opportunities

| Organization | Activity | Commitment |
|--------------|----------|------------|
| Food Bank Network | Sort/pack food | 2-4 hours weekly |
| Literacy Council | Tutor adults | 2 hours weekly |
| Senior Companion Program | Visit elderly | Flexible |
| Park Cleanup Crew | Environmental | Monthly events |
| Animal Shelter | Care for pets | Weekend shifts |

## One-Time Events

- Charity runs/walks (quarterly)
- Holiday food drives (Nov-Dec)
- Community clean-up days (spring/fall)
- School supply drives (August)

## Youth Volunteering

Ages 12-17 can volunteer with:
- Library reading programs
- Youth sports coaching assistant
- Community garden
- Peer tutoring

## How to Sign Up

1. Browse opportunities at volunteer.example.org
2. Complete orientation (online or in-person)
3. Match with organization
4. Start volunteering

## Benefits

- Meet community members
- Build skills and experience
- Flexible scheduling
- Many no experience needed

Contact: volunteer@community.example.org
""",
        },
        {
            "url": "https://health.example.gov/mental-health-resources",
            "title": "Mental Health Resources — Public Health Department",
            "topic": "health_wellness",
            "source": "Public Health Department",
            "published_date": "2025-08-01",
            "reading_level": "medium",
            "tags": ["health", "mental", "wellness", "support"],
            "snippet": "Directory of mental health resources including crisis lines, counseling options, and self-care guides.",
            "text": """# Mental Health Resources

Public Health Department — Support for Well-being

## Crisis Support

**988 Suicide & Crisis Lifeline**: Call or text 988 (24/7)
**Crisis Text Line**: Text HOME to 741741
**Local Crisis Center**: (555) 789-0123

## Counseling Options

| Type | Description | Cost |
|------|-------------|------|
| Community Mental Health | Sliding scale fees | $0-50/session |
| University Counseling | For students | Free |
| Employee Assistance | Through employer | Free (limited) |
| Private Practice | Individual therapist | $100-200/session |

## Self-Care Strategies

1. **Regular routine**: Consistent sleep, meals, activity
2. **Social connection**: Maintain relationships
3. **Physical activity**: Even 10 min helps
4. **Mindfulness**: Breathing exercises, meditation
5. **Limits**: Set boundaries on work and media

## Support Groups

- Anxiety support (weekly, free)
- Depression recovery (peer-led)
- Grief and loss (monthly)
- Parents support (flexible)

## For Families

- Family counseling services
- Youth mental health programs
- Parenting workshops
- School-based support

**Important**: If experiencing crisis, call 988 immediately.

Resources: health.example.gov/mental-health-directory
""",
        },
        {
            "url": "https://finance.example.org/smart-shopping-guide",
            "title": "Smart Shopping Guide — Consumer Finance Council",
            "topic": "budgeting",
            "source": "Consumer Finance Council",
            "published_date": "2026-01-15",
            "reading_level": "easy",
            "tags": ["shopping", "budgeting", "consumer", "tips"],
            "snippet": "Practical tips for smart shopping. Covers price comparison, avoiding impulse buys, seasonal timing.",
            "text": """# Smart Shopping Guide

Consumer Finance Council — Stretch Your Dollar

## Before You Buy

1. **Price compare**: Check at least 3 sources
2. **Read reviews**: Verified purchases preferred
3. **Wait 24 hours**: Impulse protection rule
4. **Check alternatives**: Is there a cheaper option that works?

## Timing Matters

| Category | Best Time to Buy |
|----------|------------------|
| Electronics | Black Friday, January clearance |
| Clothing | End of season (Feb/Mar, Aug/Sep) |
| Furniture | January, July |
| Appliances | Holiday weekends |
| Groceries | Weekly sales, bulk buying |

## Online Shopping Tips

- Use browser extensions for coupons (Honey, Rakuten)
- Free shipping thresholds: Consider if truly saving
- Subscribe-and-save: Good for regular items
- Price drop alerts: Set notifications

## Avoid These Traps

- "Limited time" pressure tactics
- Bundle deals you won't use
- Store credit card discounts (high interest)
- Free gift with purchase (usually overpriced)

## Grocery Specifics

- Unit price matters more than package size
- Store brands often equal quality
- Sales cycles: Track patterns
- Bulk: Only for items you actually use

Tools: price-compare.example.org
""",
        },
        {
            "url": "https://education.example.org/homework-help-resources",
            "title": "Homework Help Resources — Education Access Initiative",
            "topic": "education",
            "source": "Education Access Initiative",
            "published_date": "2025-10-01",
            "reading_level": "easy",
            "tags": ["education", "homework", "students", "help"],
            "snippet": "Free homework help resources for students and parents. Covers math, reading, science, and study skills.",
            "text": """# Homework Help Resources

Education Access Initiative — Support for Students

## Free Online Help

| Resource | Subjects | Availability |
|----------|----------|--------------|
| Khan Academy | Math, Science, History | 24/7 videos |
| Brainfuse | All subjects | Live tutors 2-11pm |
| Mathway | Math only | Step-by-step solver |
| Grammarly | Writing | Grammar/spell check |

## Library Programs

- After-school homework club (Mon-Thu 3-6pm)
- Weekend study sessions (Sat 10am-1pm)
- Summer learning programs
- Reading challenges

## For Parents

### Creating Good Environment
- Quiet, consistent workspace
- Regular homework time
- Supplies ready (paper, pencils, calculator)
- Minimize distractions

### Supporting Without Doing
- Ask "What do you think next?"
- Help break down big tasks
- Celebrate progress, not just completion
- Let mistakes happen (learning opportunity)

## Subject-Specific Tips

- **Math**: Practice problems daily, show work
- **Reading**: Discuss the story, ask questions
- **Writing**: Draft first, revise later
- **Science**: Hands-on experiments when possible

## When to Seek More Help

- Falling behind consistently
- Emotional stress around homework
- Learning gaps identified by teacher

Contact: homework-help@education.example.org
""",
        },
        {
            "url": "https://privacy.example.org/kids-online-safety",
            "title": "Kids Online Safety Guide — Privacy Foundation",
            "topic": "privacy_digital_safety",
            "source": "Privacy Foundation",
            "published_date": "2026-03-01",
            "reading_level": "easy",
            "tags": ["kids", "online", "safety", "privacy"],
            "snippet": "Age-appropriate online safety guide for children. Covers screen time, gaming, social media readiness.",
            "text": """# Kids Online Safety Guide

Privacy Foundation — Protecting Children Online

## Screen Time Guidelines

| Age | Recommended Daily Limit |
|-----|------------------------|
| Under 2 | Video chat only |
| 2-5 | 1 hour, high-quality content |
| 6-12 | 2 hours, balance with other activities |
| 13+ | Negotiate limits, prioritize sleep |

## Gaming Safety

- **Game ratings**: Check ESRB (E, T, M ratings)
- **In-game chat**: Consider disabling or monitoring
- **Time limits**: Set timers
- **Spending**: Disable or monitor purchases

## Social Media Readiness

Signs child is ready:
- Understands permanent nature of posts
- Can identify suspicious messages
- Willing to involve parent if problems
- Shows self-regulation offline

**Recommended age**: 13+ for most platforms (per COPPA)

## Communication Rules

1. Don't share full name, address, school
2. Photos: Parent approval before posting
3. Passwords: Parents should know
4.陌生人: Never meet online-only contacts

## Parent Tools

- Family Link (Android)
- Screen Time (iOS)
- Router-level controls
- Platform parental settings

**Key**: Talk regularly, not just restrict.

Resources: privacy.example.org/kids-tools
""",
        },
    ]

    def __init__(
        self,
        pages: Optional[List[Dict[str, Any]]] = None,
        initial_notes: Optional[Dict[str, Dict[str, Any]]] = None,
        research_notes: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        """Initialize toolkit with optional custom fixtures.

        Args:
            pages: List of page dicts. Defaults to DEFAULT_PAGES.
            initial_notes: Dict of pre-existing research notes.
        """
        self.pages: List[Dict[str, Any]] = copy.deepcopy(
            pages if pages is not None else self.DEFAULT_PAGES
        )
        self._page_index: Dict[str, Dict[str, Any]] = {
            p["url"]: p for p in self.pages
        }
        self.research_notes: Dict[str, Dict[str, Any]] = copy.deepcopy(
            research_notes if research_notes is not None else initial_notes if initial_notes is not None else {}
        )
        self._next_note_id: int = 1
        self._search_count: int = 0
        self._fetch_count: int = 0

    def clone(self) -> "ToolbenchWebToolkit":
        """Create a fresh toolkit reset to default state."""
        return ToolbenchWebToolkit()

    def dump_state(self) -> Dict[str, Any]:
        """Export current state including research notes."""
        return {
            "pages_count": len(self.pages),
            "topics": list(self.list_topics()["topics"]),
            "research_notes": copy.deepcopy(self.research_notes),
            "search_count": self._search_count,
            "fetch_count": self._fetch_count,
        }

    def list_tools(self) -> List[str]:
        """Return list of available tool names."""
        return [
            "search_pages",
            "fetch_page",
            "list_topics",
            "create_research_note",
            "get_research_note",
            "search_notes",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a tool by name."""
        if not hasattr(self, tool_name):
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    # === Read-Only Tools ===

    def search_pages(
        self,
        query: str,
        topic: Optional[str] = None,
        max_results: int = 5,
    ) -> Dict[str, Any]:
        """Search fixture pages by query and optional topic filter.

        Args:
            query: Search query string.
            topic: Optional topic to filter results.
            max_results: Maximum results to return (default 5).

        Returns:
            results: List of matching pages (url, title, snippet, topic).
            total: Total matches found.
            query: Original query.
        """
        self._search_count += 1
        query_lower = query.lower().strip()

        matches = []
        for page in self.pages:
            # Topic filter
            if topic and page.get("topic") != topic:
                continue

            # Query match in title, tags, or snippet
            title_lower = page.get("title", "").lower()
            snippet_lower = page.get("snippet", "").lower()
            tags_lower = [t.lower() for t in page.get("tags", [])]
            text_lower = page.get("text", "").lower()

            # Simple substring match
            if query_lower in title_lower or \
               query_lower in snippet_lower or \
               any(query_lower in t for t in tags_lower) or \
               query_lower in text_lower:
                matches.append({
                    "url": page["url"],
                    "title": page["title"],
                    "snippet": page["snippet"],
                    "topic": page["topic"],
                })

        # Sort by relevance (title match first, then snippet)
        def relevance_score(m):
            score = 0
            if query_lower in m["title"].lower():
                score += 10
            if query_lower in m["snippet"].lower():
                score += 5
            return score

        matches.sort(key=relevance_score, reverse=True)

        return {
            "results": matches[:max_results],
            "total": len(matches),
            "query": query,
            "topic_filter": topic,
        }

    def fetch_page(self, url: str) -> Dict[str, Any]:
        """Fetch full page content by URL.

        Args:
            url: URL to fetch.

        Returns:
            Full page data if found, error dict if not found.
        """
        self._fetch_count += 1
        page = self._page_index.get(url)

        if not page:
            return {
                "error": f"Page not found in fixture: {url}",
                "url": url,
            }

        return copy.deepcopy(page)

    def list_topics(self) -> Dict[str, Any]:
        """List all available topics in the fixture.

        Returns:
            topics: List of topic strings with counts.
        """
        topic_counts: Dict[str, int] = {}
        for page in self.pages:
            topic = page.get("topic", "unknown")
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

        topics_with_counts = [
            {"topic": t, "page_count": c}
            for t, c in sorted(topic_counts.items())
        ]

        return {
            "topics": [t["topic"] for t in topics_with_counts],
            "details": topics_with_counts,
        }

    # === State-Mutating Tools ===

    def create_research_note(
        self,
        title: str,
        source_urls: List[str],
        summary: str,
        key_points: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a research note from gathered sources.

        Args:
            title: Note title.
            source_urls: List of source URLs.
            summary: Summary text.
            key_points: Optional list of key points.

        Returns:
            note_id: Generated note ID.
            title: Note title.
            created_at: Creation timestamp.
        """
        note_id = f"note_{self._next_note_id:03d}"
        self._next_note_id += 1

        # Validate source URLs exist
        valid_urls = []
        invalid_urls = []
        for url in source_urls:
            if url in self._page_index:
                valid_urls.append(url)
            else:
                invalid_urls.append(url)

        self.research_notes[note_id] = {
            "title": title,
            "source_urls": valid_urls,
            "summary": summary,
            "key_points": key_points if key_points is not None else [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "invalid_urls": invalid_urls,
        }

        return {
            "note_id": note_id,
            "title": title,
            "created_at": self.research_notes[note_id]["created_at"],
            "valid_sources": len(valid_urls),
            "invalid_sources": len(invalid_urls),
        }

    def get_research_note(self, note_id: str) -> Dict[str, Any]:
        """Retrieve a research note by ID.

        Args:
            note_id: Note ID (e.g., "note_001").

        Returns:
            Full note data if found, error dict if not found.
        """
        note = self.research_notes.get(note_id)

        if not note:
            return {
                "error": f"Research note not found: {note_id}",
                "note_id": note_id,
            }

        return copy.deepcopy(note)

    def search_notes(self, query: str) -> Dict[str, Any]:
        """Search research notes by query.

        Args:
            query: Search query for note titles and summaries.

        Returns:
            results: List of matching note summaries.
        """
        query_lower = query.lower().strip()
        matches = []

        for note_id, note in self.research_notes.items():
            title_lower = note.get("title", "").lower()
            summary_lower = note.get("summary", "").lower()

            if query_lower in title_lower or query_lower in summary_lower:
                matches.append({
                    "note_id": note_id,
                    "title": note["title"],
                    "created_at": note["created_at"],
                })

        return {
            "results": matches,
            "total": len(matches),
            "query": query,
        }


def load_default_web_toolkit() -> ToolbenchWebToolkit:
    """Load a toolkit with default fixture state."""
    return ToolbenchWebToolkit()
