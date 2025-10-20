"""
Query expansion rules configuration for semantic search enhancement.
This module contains synonyms and related terms to improve query matching.
"""

EXPANSION_RULES = {
    "work": ["work", "job", "employment", "career", "experience", "professional", "occupation", "vocation"],
    "job": ["job", "work", "employment", "position", "role", "assignment", "task"],
    "career": ["career", "work", "professional", "employment", "vocation", "occupation"],
    "experience": ["experience", "work", "background", "history", "expertise", "knowledge", "skill"],
    "professional": ["professional", "work", "career", "expert", "specialist", "qualified"],
    
    "company": ["company", "organization", "firm", "employer", "business", "corporation", "enterprise"],
    "companies": ["companies", "organizations", "firms", "employers", "businesses", "corporations"],
    "organization": ["organization", "company", "firm", "institution", "association", "entity"],
    
    "before": ["before", "previous", "past", "earlier", "prior", "former", "preceding"],
    "previous": ["previous", "past", "earlier", "prior", "before", "former", "preceding"],
    "past": ["past", "previous", "earlier", "before", "former", "historic", "prior"],
    "current": ["current", "present", "ongoing", "active", "existing", "contemporary"],
    "recent": ["recent", "latest", "new", "modern", "contemporary", "current"],
    
    "education": ["education", "school", "university", "college", "degree", "study", "learning", "academic"],
    "school": ["school", "education", "university", "college", "study", "academy", "institution"],
    "university": ["university", "college", "education", "school", "degree", "study", "academy"],
    "study": ["study", "education", "school", "university", "learning", "degree", "research"],
    "degree": ["degree", "qualification", "certificate", "diploma", "education", "credential"],
    "learn": ["learn", "study", "understand", "master", "acquire", "develop", "gain"],
    
    "project": ["project", "work", "development", "build", "create", "initiative", "undertaking", "assignment"],
    "built": ["built", "developed", "created", "made", "implemented", "constructed", "engineered"],
    "develop": ["develop", "build", "create", "design", "engineer", "construct", "implement"],
    "create": ["create", "build", "develop", "design", "make", "produce", "construct"],
    "build": ["build", "develop", "create", "construct", "engineer", "make", "implement"],
    
    "technology": ["technology", "tech", "software", "system", "platform", "tool", "framework"],
    "skill": ["skill", "ability", "expertise", "competence", "proficiency", "capability", "talent"],
    "technical": ["technical", "technological", "engineering", "scientific", "specialized", "expert"],
    "programming": ["programming", "coding", "development", "software", "engineering", "scripting"],
    "code": ["code", "program", "develop", "script", "implement", "engineer"],
    
    "portfolio": ["portfolio", "showcase", "collection", "work", "projects", "examples", "demonstrations"],
    "showcase": ["showcase", "portfolio", "display", "demonstrate", "exhibit", "present", "feature"],
    
    "contact": ["contact", "reach", "connect", "message", "email", "communicate", "get in touch"],
    "email": ["email", "message", "contact", "reach", "communicate", "correspond"],
    "linkedin": ["linkedin", "professional", "network", "social", "profile", "connect"],
    "github": ["github", "code", "repository", "projects", "source", "programming"],
    
    "achievement": ["achievement", "accomplishment", "success", "milestone", "result", "outcome"],
    "success": ["success", "achievement", "accomplishment", "result", "outcome", "victory"],
    "accomplish": ["accomplish", "achieve", "complete", "finish", "succeed", "attain", "realize"],
    
    "solve": ["solve", "resolve", "fix", "address", "tackle", "overcome", "handle"],
    "problem": ["problem", "issue", "challenge", "difficulty", "obstacle", "barrier"],
    "solution": ["solution", "answer", "resolution", "fix", "remedy", "approach"],
    
    "team": ["team", "group", "collaboration", "partnership", "crew", "squad"],
    "collaborate": ["collaborate", "work together", "cooperate", "partner", "team up", "join forces"],
    "lead": ["lead", "manage", "direct", "guide", "supervise", "oversee", "coordinate"],
    
    "finance": ["finance", "banking", "financial", "investment", "money", "capital"],
    "technology": ["technology", "tech", "software", "IT", "computing", "digital"],
    "education": ["education", "learning", "academic", "teaching", "instruction", "training"],
    "gaming": ["gaming", "games", "entertainment", "interactive", "video games", "play"],
    "blockchain": ["blockchain", "crypto", "cryptocurrency", "web3", "decentralized", "NFT"],
    
    "about": ["about", "information", "details", "background", "profile", "overview"],
    "background": ["background", "history", "experience", "education", "qualifications", "profile"],
    "interest": ["interest", "hobby", "passion", "enthusiasm", "curiosity", "fascination"],

    "go": ["go", "navigate", "find", "access", "visit", "open", "explore"]
}