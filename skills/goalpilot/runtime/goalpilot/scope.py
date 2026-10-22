"""Conservative local routing for missions with many explicit workstreams."""
import re


def completion_review(goal, original):
    """Return observable routing evidence, without an extra model call.

    This is a scope heuristic, not a classifier trained on benchmark outcomes.
    Explicit thorough mode always wins. Small missions keep the adaptive path.
    """
    sections=re.findall(r'^##\s+(.+)',original,re.MULTILINE)
    broad=bool(re.search(r'\b(platform|plateforme|end.to.end|de bout en bout|whole|complet[e]?)\b',goal,re.IGNORECASE))
    required=len(sections)>=8 and len(original)>=3000 or broad and len(sections)>=5 and len(original)>=2000
    return {'required':required,'sections':sections,'original_contract_characters':len(original),
            'reason':'Many explicit workstreams require independent end-to-end completion checks' if required else 'Local delivery verification with recovery remains appropriate'}
