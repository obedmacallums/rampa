"""Latest-per-option artifact resolution across a survey's runs (FR-016).

For each option ever selected on a survey, the displayed product is the
artifact of the latest run whose RunOption(option_id) is `completed`;
`reused` rows delegate to `reused_from` (already resolved transitively when
they were created, R5). No denormalized "current artifact" pointer — this is
a plain query over RunOption + DerivedArtifact evaluated at read time.
"""

from .models import DerivedArtifact, ProcessingRun, RunOption, Survey


def resolve_products(survey: Survey) -> dict[str, tuple[DerivedArtifact, ProcessingRun]]:
    resolved: dict[str, tuple[DerivedArtifact, ProcessingRun]] = {}
    for run in survey.runs.order_by("-number").prefetch_related("options", "artifacts"):
        for run_opt in run.options.all():
            option_id = run_opt.option_id
            if option_id in resolved:
                continue
            producing_run = None
            if run_opt.state == RunOption.State.COMPLETED:
                producing_run = run
            elif run_opt.state == RunOption.State.REUSED and run_opt.reused_from_id:
                producing_run = run_opt.reused_from
            if producing_run is None:
                continue
            artifact = next(
                (a for a in producing_run.artifacts.all() if a.option_id == option_id), None
            )
            if artifact is not None:
                resolved[option_id] = (artifact, producing_run)
    return resolved
