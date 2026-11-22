from fractions import Fraction

from calibration.revisions import SealedRevision
from issue.encoding import PublicBody, PublicState


def build_public_body(revision: SealedRevision) -> PublicBody:
    weights = {}
    for state in revision.states:
        distribution = tuple(sorted((outlet, mass) for outlet, mass in state.outlets if mass))
        # Equal whole distributions have equal behavior over any number of visits.
        weights[distribution] = weights.get(distribution, Fraction(0)) + state.weight
    states = tuple(PublicState(weight, distribution) for distribution, weight in sorted(weights.items()))
    return PublicBody(tuple(sorted(revision.outlets)), states)
