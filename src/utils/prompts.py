"""LLM prompt templates for various operations."""

JOB_EXTRACTION_PROMPT = """You are an HR analysis expert. Extract structured information from the following job description.

Job Description:
{job_description}

Please extract and return a JSON object with the following fields:
- title: Job title (string)
- required_skills: List of required technical skills (array of strings)
- preferred_skills: List of preferred/nice-to-have skills (array of strings)
- experience_years: Required years of experience as a STRING (e.g., "5+", "3-5", "0" for entry level)
- education: Required education level (string)
- responsibilities: List of key responsibilities (array of strings)
- requirements: List of other requirements (array of strings)

IMPORTANT:
- Return ONLY valid JSON, no markdown code blocks or extra text
- experience_years must be a STRING, not a number
- If you can't find information, use empty string "" or empty array []

Example output format:
{{
  "title": "Senior Python Developer",
  "required_skills": ["Python", "FastAPI", "Docker"],
  "preferred_skills": ["React", "AWS"],
  "experience_years": "5+",
  "education": "Bachelor's degree in Computer Science",
  "responsibilities": ["Design scalable backend services", "Write clean code"],
  "requirements": ["Strong problem-solving skills"]
}}
"""

CV_EXTRACTION_PROMPT = """You are an HR analysis expert. Extract structured information from the following CV/Resume.

CV Text:
{cv_text}

Please extract and return a JSON object with the following fields:
- name: Candidate full name (string, IMPORTANT: extract the EXACT name as written
  in the CV. Do NOT add diacritics, do NOT guess Vietnamese tone marks, do NOT
  correct spelling. If the CV says "Nguyen Van A", return "Nguyen Van A"
  exactly, NOT "Nguyễn Văn A")
- email: Email address if available (string)
- phone: Phone number if available (string)
- skills: List of technical skills mentioned (array of strings)
- experience_years: Total years of professional experience as a NUMBER (integer). Calculate from work history dates if not explicitly stated. If unclear, use 0.
- education: Highest education level and degree (string)
- work_history: List of previous roles with company, title, brief description (array of strings)
- summary: Brief professional summary in 2-3 sentences (string)

IMPORTANT:
- Return ONLY valid JSON, no markdown code blocks or extra text
- Extract the ACTUAL candidate name from the CV text EXACTLY as written, preserving original spelling and capitalization
- Do NOT add Vietnamese diacritics/tone marks to names if the CV doesn't have them
- If you can't find a field, use empty string "" or empty array [] or 0 for numbers
- experience_years MUST be an integer NUMBER (e.g., 5), not a string (e.g., "5 years")
- Calculate experience_years from work history date ranges if not explicitly stated

Example output format:
{{
  "name": "Nguyen Van A",
  "email": "candidate email",
  "phone": "candidate phone",
  "skills": ["Python", "FastAPI", "Docker", "PostgreSQL"],
  "experience_years": 6,
  "education": "Bachelor of Computer Science",
  "work_history": ["Senior Developer at Company X (2020-2024)", "Developer at Company Y (2018-2020)"],
  "summary": "Experienced Python developer with 6 years in backend development. Strong expertise in FastAPI and Docker."
}}
"""

MATCHING_PROMPT = """You are an expert HR recruiter evaluating how well a candidate matches a job position.

Job Requirements:
{job_requirements}

Candidate Profile:
{candidate_profile}

Analyze this candidate's fit for the position by evaluating:

1. **Required Skills Match**: How many of the required skills does the candidate have?
2. **Experience Level**: Does their experience years and seniority match the job requirements?
3. **Education Match**: Does their education meet the requirements?
4. **Technical Depth**: Do they have hands-on experience with the key technologies?
5. **Overall Fit**: Considering all factors, how well suited are they?

Scoring Guidelines:
- 90-100: Excellent match - meets all or almost all requirements, strong experience
- 80-89: Very good match - meets most requirements, solid background
- 70-79: Good match - meets core requirements, some gaps in preferred skills
- 60-69: Fair match - meets basic requirements, several gaps
- 50-59: Weak match - meets some requirements, significant gaps
- 0-49: Poor match - lacks critical requirements

Provide your analysis in JSON format with these fields:
- fit_score: Integer from 0-100 (be realistic and precise based on actual match)
- strengths: Array of 3-5 specific strengths (skills/experience that match well)
- gaps: Array of 2-4 specific gaps (requirements the candidate lacks)
- reasoning: Brief 2-3 sentence explanation for the score

IMPORTANT:
- Return ONLY valid JSON, no markdown code blocks
- fit_score must be an INTEGER (not string), based on actual skill/experience overlap
- Be specific in strengths/gaps (mention actual skills/technologies)
- Don't be overly generous - only excellent candidates should score above 85
- LANGUAGE RULE: Write strengths, gaps, and reasoning in the SAME language as
  the Job Requirements above. If the job description is in Vietnamese, respond
  in Vietnamese. If in English, respond in English.

Example output (English job):
{{
  "fit_score": 82,
  "strengths": [
    "6 years Python experience exceeds 5+ year requirement",
    "Strong FastAPI and Django expertise matches core tech stack",
    "Proven Docker and Kubernetes experience for microservices"
  ],
  "gaps": [
    "No AWS cloud experience mentioned (required)",
    "Limited PostgreSQL database optimization background"
  ],
  "reasoning": "Strong match with excellent Python backend experience and modern framework knowledge. Main gap is cloud infrastructure experience which is critical for this role."
}}

Example output (Vietnamese job):
{{
  "fit_score": 75,
  "strengths": [
    "5 năm kinh nghiệm Python đáp ứng yêu cầu 3+ năm",
    "Thành thạo FastAPI và Django phù hợp với tech stack",
    "Có kinh nghiệm triển khai Docker container"
  ],
  "gaps": [
    "Chưa có kinh nghiệm AWS cloud (yêu cầu bắt buộc)",
    "Thiếu kinh nghiệm tối ưu hóa PostgreSQL"
  ],
  "reasoning": "Ứng viên có nền tảng Python tốt và kinh nghiệm framework hiện đại. Điểm yếu chính là thiếu kinh nghiệm cloud infrastructure, vốn là yêu cầu quan trọng cho vị trí này."
}}
"""

QUESTION_GENERATION_PROMPT = """You are an expert technical interviewer creating tailored interview questions for a candidate.

Job Position:
{job_title}

Job Requirements:
{job_requirements}

Candidate Profile:
{candidate_profile}

Matching Analysis:
{matching_context}

Generate 10-12 diverse interview questions that:

1. **Technical Questions (5-6 questions)**:
   - Test specific technologies/frameworks mentioned in requirements (e.g., Python, FastAPI, Docker, AWS)
   - Probe depth of experience with required skills
   - Include scenario-based technical problems
   - Cover system design and architecture understanding
   - **IMPORTANT**: For strengths listed in matching analysis, create questions to VALIDATE and probe DEPTH
   - **IMPORTANT**: For gaps, create questions to assess adaptability and learning capacity

2. **Behavioral Questions (3-4 questions)**:
   - Explore past experiences relevant to the role
   - Test soft skills (teamwork, leadership, communication)
   - Understand approach to challenges and failures
   - Assess cultural fit
   - Reference candidate's actual work history and achievements

3. **Situational Questions (2-3 questions)**:
   - Present hypothetical scenarios from the job description
   - Test problem-solving approach
   - Evaluate decision-making process
   - **IMPORTANT**: Focus on gaps - give candidate opportunity to show how they'd handle missing skills
   - Create realistic scenarios based on actual job responsibilities

Guidelines:
- Make questions SPECIFIC to the candidate's background (reference their actual experience)
- Use matching analysis to prioritize question topics (strengths + gaps)
- Include technical depth appropriate for the seniority level
- Mix easy, medium, and hard questions
- Avoid generic questions that could apply to any candidate
- For strengths: Test depth with advanced scenarios
- For gaps: Test adaptability with learning-focused questions

Return a JSON array of 10-12 question objects, each with:
- question: The interview question text (string)
- type: "Technical" | "Behavioral" | "Situational" (string)
- focus_area: The skill/area being tested (string)
- difficulty: "Easy" | "Medium" | "Hard" (string)

IMPORTANT:
- Return ONLY valid JSON array, no markdown code blocks
- Generate EXACTLY 10-12 questions (not fewer)
- Make each question unique and specific
- Leverage matching analysis to make questions more targeted
- LANGUAGE RULE: Write ALL questions, focus_area, and content in the SAME
  language as the Job Requirements above. If the job description is in
  Vietnamese, write questions in Vietnamese. If in English, write in English.

Example output format:
[
  {{
    "question": "You mentioned 6 years of FastAPI experience, which is a key strength. "
                 "Can you walk me through how you would design a rate-limiting system "
                 "for a high-traffic API handling 10K requests/second?",
    "type": "Technical",
    "focus_area": "FastAPI & System Design",
    "difficulty": "Hard"
  }},
  {{
    "question": "In your role at TechCorp, you led a team of 3 developers. How did you handle a situation where team members disagreed on a technical approach?",
    "type": "Behavioral",
    "focus_area": "Leadership & Conflict Resolution",
    "difficulty": "Medium"
  }},
  {{
    "question": "The job requires AWS experience, which is a gap in your profile. "
                 "If you needed to migrate our current on-premise PostgreSQL database to AWS RDS, "
                 "what would be your learning approach and initial steps?",
    "type": "Situational",
    "focus_area": "Cloud Migration & Gap Analysis",
    "difficulty": "Hard"
  }}
]
"""
