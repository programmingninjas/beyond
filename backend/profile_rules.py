"""Profile completion rules; weights are provisional product defaults."""
from urllib.parse import urlparse

EXTRA_FIELDS = ('headline', 'role', 'organization', 'skills', 'expertise', 'industry', 'projects', 'experience', 'achievements', 'website', 'additional_social', 'networking_goals')


def valid_url(value):
    parsed = urlparse((value or '').strip())
    return parsed.scheme in ('http', 'https') and bool(parsed.netloc)


def completion(user, data):
    about = (user.bio or '').strip()
    basic = {
        'name': bool((user.name or '').strip()),
        'email': bool((user.email or '').strip()),
        'phone': len(''.join(c for c in data.get('phone', '') if c.isdigit())) >= 7,
        'social_profile': valid_url(user.profile_url),
        'about_me': 100 <= len(about) <= 1000,
        'interests': any(x.strip() for x in (user.interests or '').split(',')),
    }
    complete = all(basic.values())
    extras = {key: bool(str(data.get(key, '')).strip()) for key in EXTRA_FIELDS}
    quiz = bool(data.get('personality_result'))
    score = (25 if complete else 0) + 5 * sum(extras.values()) + (15 if quiz else 0)
    # The required section must be complete before optional fields can grant access.
    return {'score': score, 'basic_complete': complete, 'missing_basic': [key for key, value in basic.items() if not value], 'extra_fields': extras, 'personality_complete': quiz, 'complete': score == 100}
