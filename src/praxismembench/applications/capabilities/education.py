"""
ToolbenchEducationToolkit - Mock education domain toolkit for SOP workbench.

Provides course catalog, learning materials, practice questions, and study plan
capabilities for evaluating learning preferences and educational resource planning.
"""

from typing import Optional
import copy


def load_default_education_toolkit():
    """Factory function to create a toolkit with default fixture."""
    return ToolbenchEducationToolkit()


class ToolbenchEducationToolkit:
    """
    Mock education toolkit supporting:
    - Course search and lookup
    - Learning materials search
    - Practice questions by subject/level
    - Study plan state management
    """

    def __init__(
        self,
        courses: Optional[dict] = None,
        materials: Optional[dict] = None,
        questions: Optional[dict] = None,
        study_plans: Optional[dict] = None,
    ):
        self._courses = copy.deepcopy(courses) if courses is not None else self._build_course_fixture()
        self._materials = copy.deepcopy(materials) if materials is not None else self._build_material_fixture()
        self._questions = copy.deepcopy(questions) if questions is not None else self._build_question_fixture()
        self._study_plans = copy.deepcopy(study_plans) if study_plans is not None else {}

    def _build_course_fixture(self):
        """Build 10 courses covering test scenarios."""
        return {
            "course_001": {
                "id": "course_001",
                "title": "Python for Beginners",
                "subject": "programming",
                "level": "beginner",
                "lesson_minutes": 15,
                "format": "video",
                "tags": ["hands-on", "short_lessons", "example_driven"],
                "summary": "Introductory Python with short video lessons and practical examples.",
            },
            "course_002": {
                "id": "course_002",
                "title": "Advanced Data Structures",
                "subject": "programming",
                "level": "advanced",
                "lesson_minutes": 45,
                "format": "video",
                "tags": ["theory_heavy", "challenging", "deep_dive"],
                "summary": "Deep dive into complex data structures with theoretical foundations.",
            },
            "course_003": {
                "id": "course_003",
                "title": "Math Fundamentals",
                "subject": "math",
                "level": "beginner",
                "lesson_minutes": 20,
                "format": "interactive",
                "tags": ["beginner_friendly", "step_by_step", "practice_oriented"],
                "summary": "Core math concepts with interactive exercises and immediate feedback.",
            },
            "course_004": {
                "id": "course_004",
                "title": "Linear Algebra Deep Dive",
                "subject": "math",
                "level": "advanced",
                "lesson_minutes": 50,
                "format": "article",
                "tags": ["advanced", "reading_intensive", "proofs"],
                "summary": "Comprehensive linear algebra for advanced learners who prefer reading.",
            },
            "course_005": {
                "id": "course_005",
                "title": "Introduction to Physics",
                "subject": "science",
                "level": "beginner",
                "lesson_minutes": 25,
                "format": "video",
                "tags": ["visual", "conceptual", "everyday_examples"],
                "summary": "Physics basics with visual demonstrations and relatable examples.",
            },
            "course_006": {
                "id": "course_006",
                "title": "Organic Chemistry Mastery",
                "subject": "science",
                "level": "intermediate",
                "lesson_minutes": 35,
                "format": "video",
                "tags": ["structured", "medium_depth", "application_focused"],
                "summary": "Organic chemistry mechanisms with structured video explanations.",
            },
            "course_007": {
                "id": "course_007",
                "title": "Quick Grammar Essentials",
                "subject": "language",
                "level": "beginner",
                "lesson_minutes": 10,
                "format": "worksheet",
                "tags": ["short_lessons", "practice_driven", "beginner_friendly"],
                "summary": "Essential grammar rules with quick worksheet exercises.",
            },
            "course_008": {
                "id": "course_008",
                "title": "Advanced Writing Techniques",
                "subject": "language",
                "level": "advanced",
                "lesson_minutes": 40,
                "format": "reading",
                "tags": ["reading_intensive", "deep_analysis", "style_development"],
                "summary": "Advanced composition and style analysis for serious writers.",
            },
            "course_009": {
                "id": "course_009",
                "title": "Teaching Python to Kids",
                "subject": "programming",
                "level": "intermediate",
                "lesson_minutes": 20,
                "format": "video",
                "tags": ["teaching_oriented", "visual", "simple_examples"],
                "summary": "Methods for teaching programming concepts to young learners.",
            },
            "course_010": {
                "id": "course_010",
                "title": "History of Computing",
                "subject": "history",
                "level": "intermediate",
                "lesson_minutes": 30,
                "format": "reading",
                "tags": ["reading_intensive", "story_driven", "contextual"],
                "summary": "Evolution of computing technology from early machines to modern systems.",
            },
        }

    def _build_material_fixture(self):
        """Build 15 learning materials covering test scenarios."""
        return {
            "material_001": {
                "id": "material_001",
                "title": "Python Quick Reference Sheet",
                "subject": "programming",
                "level": "beginner",
                "format_type": "worksheet",
                "estimated_minutes": 5,
                "tags": ["quick_reference", "beginner_friendly", "short"],
                "summary": "One-page reference for common Python syntax and operations.",
            },
            "material_002": {
                "id": "material_002",
                "title": "Understanding Variables Video",
                "subject": "programming",
                "level": "beginner",
                "format_type": "video",
                "estimated_minutes": 8,
                "tags": ["example_driven", "visual", "beginner_friendly"],
                "summary": "Visual explanation of variables with concrete examples.",
            },
            "material_003": {
                "id": "material_003",
                "title": "Algorithm Design Patterns Article",
                "subject": "programming",
                "level": "advanced",
                "format_type": "article",
                "estimated_minutes": 25,
                "tags": ["reading_intensive", "theory_first", "deep_dive"],
                "summary": "Comprehensive article on algorithmic patterns before examples.",
            },
            "material_004": {
                "id": "material_004",
                "title": "Math Problem Set: Fractions",
                "subject": "math",
                "level": "beginner",
                "format_type": "worksheet",
                "estimated_minutes": 15,
                "tags": ["practice_oriented", "beginner_friendly", "short"],
                "summary": "Practice problems for fraction operations with solutions.",
            },
            "material_005": {
                "id": "material_005",
                "title": "Calculus Interactive Tutorial",
                "subject": "math",
                "level": "intermediate",
                "format_type": "interactive",
                "estimated_minutes": 30,
                "tags": ["interactive", "step_by_step", "example_driven"],
                "summary": "Interactive calculus concepts with guided examples first.",
            },
            "material_006": {
                "id": "material_006",
                "title": "Physics Lab Simulations",
                "subject": "science",
                "level": "intermediate",
                "format_type": "interactive",
                "estimated_minutes": 20,
                "tags": ["interactive", "visual", "experiment_oriented"],
                "summary": "Virtual lab experiments for physics concepts.",
            },
            "material_007": {
                "id": "material_007",
                "title": "Chemistry Video Series: Reactions",
                "subject": "science",
                "level": "beginner",
                "format_type": "video",
                "estimated_minutes": 12,
                "tags": ["visual", "short", "beginner_friendly"],
                "summary": "Short videos demonstrating common chemical reactions.",
            },
            "material_008": {
                "id": "material_008",
                "title": "Grammar Cheat Sheet",
                "subject": "language",
                "level": "beginner",
                "format_type": "worksheet",
                "estimated_minutes": 3,
                "tags": ["quick_reference", "short", "beginner_friendly"],
                "summary": "Essential grammar rules on one printable sheet.",
            },
            "material_009": {
                "id": "material_009",
                "title": "Essay Writing Guide",
                "subject": "language",
                "level": "intermediate",
                "format_type": "article",
                "estimated_minutes": 20,
                "tags": ["reading_intensive", "structured", "practice_oriented"],
                "summary": "Step-by-step guide for constructing well-structured essays.",
            },
            "material_010": {
                "id": "material_010",
                "title": "Teaching Resources Collection",
                "subject": "pedagogy",
                "level": "intermediate",
                "format_type": "article",
                "estimated_minutes": 15,
                "tags": ["teaching_oriented", "practical", "classroom_ready"],
                "summary": "Collection of teaching strategies and classroom activities.",
            },
            "material_011": {
                "id": "material_011",
                "title": "Advanced Math Problems Challenge",
                "subject": "math",
                "level": "advanced",
                "format_type": "worksheet",
                "estimated_minutes": 45,
                "tags": ["challenging", "theory_first", "deep_dive"],
                "summary": "Challenging problems requiring strong theoretical foundations.",
            },
            "material_012": {
                "id": "material_012",
                "title": "Programming Examples Before Theory",
                "subject": "programming",
                "level": "beginner",
                "format_type": "video",
                "estimated_minutes": 10,
                "tags": ["example_driven", "beginner_friendly", "short"],
                "summary": "Code examples introduced before theoretical explanations.",
            },
            "material_013": {
                "id": "material_013",
                "title": "Reading Comprehension Exercises",
                "subject": "language",
                "level": "beginner",
                "format_type": "worksheet",
                "estimated_minutes": 10,
                "tags": ["reading_oriented", "beginner_friendly", "practice_oriented"],
                "summary": "Short passages with comprehension questions for beginners.",
            },
            "material_014": {
                "id": "material_014",
                "title": "Scientific Method Reading",
                "subject": "science",
                "level": "intermediate",
                "format_type": "reading",
                "estimated_minutes": 18,
                "tags": ["reading_intensive", "structured", "theory_first"],
                "summary": "Detailed reading on scientific methodology and process.",
            },
            "material_015": {
                "id": "material_015",
                "title": "Time-Saving Study Tips",
                "subject": "study_skills",
                "level": "beginner",
                "format_type": "article",
                "estimated_minutes": 8,
                "tags": ["short", "practical", "time_efficient"],
                "summary": "Quick tips for efficient studying with limited time.",
            },
        }

    def _build_question_fixture(self):
        """Build 16 practice questions covering test scenarios."""
        return {
            "q_001": {
                "id": "q_001",
                "subject": "programming",
                "level": "beginner",
                "question": "What is the output of print(2 + 3)?",
                "options": ["5", "23", "2+3", "error"],
                "answer": "5",
                "explanation": "Python evaluates the expression 2 + 3 and prints the result.",
            },
            "q_002": {
                "id": "q_002",
                "subject": "programming",
                "level": "beginner",
                "question": "Which keyword defines a function in Python?",
                "options": ["func", "def", "function", "define"],
                "answer": "def",
                "explanation": "Python uses 'def' keyword to define functions.",
            },
            "q_003": {
                "id": "q_003",
                "subject": "programming",
                "level": "intermediate",
                "question": "What does list comprehension [x*2 for x in range(3)] produce?",
                "options": ["[0, 2, 4]", "[2, 4, 6]", "[0, 1, 2]", "[1, 2, 3]"],
                "answer": "[0, 2, 4]",
                "explanation": "range(3) gives 0,1,2; each doubled gives 0,2,4.",
            },
            "q_004": {
                "id": "q_004",
                "subject": "programming",
                "level": "advanced",
                "question": "What is the time complexity of merge sort?",
                "options": ["O(n)", "O(n log n)", "O(n^2)", "O(log n)"],
                "answer": "O(n log n)",
                "explanation": "Merge sort divides and conquers, achieving O(n log n) in all cases.",
            },
            "q_005": {
                "id": "q_005",
                "subject": "math",
                "level": "beginner",
                "question": "What is 15 divided by 3?",
                "options": ["3", "5", "15", "45"],
                "answer": "5",
                "explanation": "15 / 3 = 5.",
            },
            "q_006": {
                "id": "q_006",
                "subject": "math",
                "level": "beginner",
                "question": "What is the sum of angles in a triangle?",
                "options": ["90 degrees", "180 degrees", "270 degrees", "360 degrees"],
                "answer": "180 degrees",
                "explanation": "The interior angles of any triangle sum to 180 degrees.",
            },
            "q_007": {
                "id": "q_007",
                "subject": "math",
                "level": "intermediate",
                "question": "What is the derivative of x^3?",
                "options": ["x^2", "3x^2", "3x", "x^3"],
                "answer": "3x^2",
                "explanation": "Using the power rule: d/dx(x^n) = n*x^(n-1).",
            },
            "q_008": {
                "id": "q_008",
                "subject": "math",
                "level": "advanced",
                "question": "What is the determinant of a 2x2 matrix [[a,b],[c,d]]?",
                "options": ["a+b+c+d", "ad-bc", "ac-bd", "ab+cd"],
                "answer": "ad-bc",
                "explanation": "Determinant of [[a,b],[c,d]] is calculated as ad - bc.",
            },
            "q_009": {
                "id": "q_009",
                "subject": "science",
                "level": "beginner",
                "question": "What is the chemical formula for water?",
                "options": ["H2O", "CO2", "O2", "NaCl"],
                "answer": "H2O",
                "explanation": "Water consists of two hydrogen atoms and one oxygen atom.",
            },
            "q_010": {
                "id": "q_010",
                "subject": "science",
                "level": "beginner",
                "question": "Which planet is closest to the Sun?",
                "options": ["Earth", "Mars", "Mercury", "Venus"],
                "answer": "Mercury",
                "explanation": "Mercury is the first planet from the Sun in our solar system.",
            },
            "q_011": {
                "id": "q_011",
                "subject": "science",
                "level": "intermediate",
                "question": "What type of bond holds NaCl together?",
                "options": ["covalent", "ionic", "metallic", "hydrogen"],
                "answer": "ionic",
                "explanation": "NaCl forms through ionic bonding between sodium and chlorine ions.",
            },
            "q_012": {
                "id": "q_012",
                "subject": "science",
                "level": "advanced",
                "question": "What is the equation for kinetic energy?",
                "options": ["mv", "1/2mv^2", "mgh", "1/2mv"],
                "answer": "1/2mv^2",
                "explanation": "Kinetic energy = 1/2 * mass * velocity squared.",
            },
            "q_013": {
                "id": "q_013",
                "subject": "language",
                "level": "beginner",
                "question": "Which sentence is correct?",
                "options": ["She don't like it", "She doesn't likes it", "She doesn't like it", "She not like it"],
                "answer": "She doesn't like it",
                "explanation": "Correct negative form uses 'doesn't' with base verb.",
            },
            "q_014": {
                "id": "q_014",
                "subject": "language",
                "level": "intermediate",
                "question": "What is a synonym for 'happy'?",
                "options": ["sad", "joyful", "angry", "tired"],
                "answer": "joyful",
                "explanation": "Joyful means feeling or expressing great pleasure and happiness.",
            },
            "q_015": {
                "id": "q_015",
                "subject": "language",
                "level": "advanced",
                "question": "What literary device uses exaggeration for effect?",
                "options": ["metaphor", "hyperbole", "simile", "irony"],
                "answer": "hyperbole",
                "explanation": "Hyperbole is exaggerated statements not meant literally.",
            },
            "q_016": {
                "id": "q_016",
                "subject": "history",
                "level": "intermediate",
                "question": "When was the first electronic computer built?",
                "options": ["1920s", "1940s", "1960s", "1980s"],
                "answer": "1940s",
                "explanation": "ENIAC, the first general-purpose electronic computer, was built in 1945.",
            },
        }

    def list_tools(self) -> list[str]:
        """Return available tool names."""
        return [
            "search_courses",
            "get_course",
            "search_materials",
            "get_material",
            "get_practice_questions",
            "create_study_plan",
            "get_study_plan",
        ]

    def invoke_tool(self, tool_name: str, **kwargs):
        """Invoke a tool by name with kwargs."""
        tool_map = {
            "search_courses": self._search_courses,
            "get_course": self._get_course,
            "search_materials": self._search_materials,
            "get_material": self._get_material,
            "get_practice_questions": self._get_practice_questions,
            "create_study_plan": self._create_study_plan,
            "get_study_plan": self._get_study_plan,
        }
        if tool_name not in tool_map:
            raise ValueError(f"Unknown tool: {tool_name}")
        return tool_map[tool_name](**kwargs)

    def _search_courses(
        self,
        query: str = "",
        subject: Optional[str] = None,
        level: Optional[str] = None,
        max_minutes_per_lesson: Optional[int] = None,
    ) -> list[dict]:
        """Search courses by query, subject, level, and lesson duration."""
        results = []
        query_lower = query.lower() if query else ""
        for item in self._courses.values():
            if subject and item.get("subject") != subject:
                continue
            if level and item.get("level") != level:
                continue
            if max_minutes_per_lesson:
                if item.get("lesson_minutes", 999) > max_minutes_per_lesson:
                    continue
            if query_lower:
                searchable = (
                    item.get("title", "").lower() + " " +
                    item.get("summary", "").lower() + " " +
                    " ".join(item.get("tags", [])).lower()
                )
                if query_lower not in searchable:
                    continue
            results.append({
                "id": item["id"],
                "title": item["title"],
                "subject": item["subject"],
                "level": item["level"],
                "lesson_minutes": item["lesson_minutes"],
                "format": item["format"],
                "tags": item.get("tags", []),
            })
        return results

    def _get_course(self, course_id: str) -> Optional[dict]:
        """Get full course details by ID."""
        course = self._courses.get(course_id)
        if course:
            return copy.deepcopy(course)
        return None

    def _search_materials(
        self,
        query: str = "",
        subject: Optional[str] = None,
        format_type: Optional[str] = None,
        level: Optional[str] = None,
    ) -> list[dict]:
        """Search learning materials by query, subject, format, and level."""
        results = []
        query_lower = query.lower() if query else ""
        for item in self._materials.values():
            if subject and item.get("subject") != subject:
                continue
            if format_type and item.get("format_type") != format_type:
                continue
            if level and item.get("level") != level:
                continue
            if query_lower:
                searchable = (
                    item.get("title", "").lower() + " " +
                    item.get("summary", "").lower() + " " +
                    " ".join(item.get("tags", [])).lower()
                )
                if query_lower not in searchable:
                    continue
            results.append({
                "id": item["id"],
                "title": item["title"],
                "subject": item["subject"],
                "level": item["level"],
                "format_type": item["format_type"],
                "estimated_minutes": item["estimated_minutes"],
                "tags": item.get("tags", []),
            })
        return results

    def _get_material(self, material_id: str) -> Optional[dict]:
        """Get full material details by ID."""
        material = self._materials.get(material_id)
        if material:
            return copy.deepcopy(material)
        return None

    def _get_practice_questions(
        self,
        subject: str,
        level: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Get practice questions filtered by subject and optionally level."""
        results = []
        for item in self._questions.values():
            if item.get("subject") != subject:
                continue
            if level and item.get("level") != level:
                continue
            results.append({
                "id": item["id"],
                "subject": item["subject"],
                "level": item["level"],
                "question": item["question"],
                "options": item["options"],
            })
        return results[:limit]

    def _create_study_plan(
        self,
        name: str,
        course_ids: Optional[list[str]] = None,
        material_ids: Optional[list[str]] = None,
        constraints_note: str = "",
    ) -> dict:
        """Create a new study plan."""
        plan_id = f"plan_{len(self._study_plans) + 1}"
        self._study_plans[plan_id] = {
            "name": name,
            "course_ids": course_ids or [],
            "material_ids": material_ids or [],
            "constraints_note": constraints_note,
        }
        return {
            "plan_id": plan_id,
            "name": name,
            "course_count": len(course_ids or []),
            "material_count": len(material_ids or []),
        }

    def _get_study_plan(self, plan_id: str) -> Optional[dict]:
        """Get study plan details with resolved course/material info."""
        plan = self._study_plans.get(plan_id)
        if not plan:
            return None
        # Resolve course and material details
        courses = []
        for cid in plan["course_ids"]:
            course = self._courses.get(cid)
            if course:
                courses.append({
                    "id": cid,
                    "title": course["title"],
                    "lesson_minutes": course["lesson_minutes"],
                })
        materials = []
        for mid in plan["material_ids"]:
            material = self._materials.get(mid)
            if material:
                materials.append({
                    "id": mid,
                    "title": material["title"],
                    "estimated_minutes": material["estimated_minutes"],
                })
        return {
            "plan_id": plan_id,
            "name": plan["name"],
            "constraints_note": plan["constraints_note"],
            "courses": courses,
            "materials": materials,
        }

    def dump_state(self) -> dict:
        """Dump current toolkit state including study plans."""
        return {
            "course_count": len(self._courses),
            "material_count": len(self._materials),
            "question_count": len(self._questions),
            "study_plans": copy.deepcopy(self._study_plans),
        }

    def clone(self):
        """Create a fresh toolkit instance (default state, no study plans)."""
        return ToolbenchEducationToolkit()

    # Public method wrappers (for direct invocation)
    def search_courses(
        self,
        query: str = "",
        subject: Optional[str] = None,
        level: Optional[str] = None,
        max_minutes_per_lesson: Optional[int] = None,
    ) -> list[dict]:
        return self._search_courses(query, subject, level, max_minutes_per_lesson)

    def get_course(self, course_id: str) -> Optional[dict]:
        return self._get_course(course_id)

    def search_materials(
        self,
        query: str = "",
        subject: Optional[str] = None,
        format_type: Optional[str] = None,
        level: Optional[str] = None,
    ) -> list[dict]:
        return self._search_materials(query, subject, format_type, level)

    def get_material(self, material_id: str) -> Optional[dict]:
        return self._get_material(material_id)

    def get_practice_questions(
        self,
        subject: str,
        level: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        return self._get_practice_questions(subject, level, limit)

    def create_study_plan(
        self,
        name: str,
        course_ids: Optional[list[str]] = None,
        material_ids: Optional[list[str]] = None,
        constraints_note: str = "",
    ) -> dict:
        return self._create_study_plan(name, course_ids, material_ids, constraints_note)

    def get_study_plan(self, plan_id: str) -> Optional[dict]:
        return self._get_study_plan(plan_id)
