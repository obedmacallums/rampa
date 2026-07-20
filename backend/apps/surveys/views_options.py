"""Processing options catalog endpoint (contracts/rest-api.md)."""

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import ApiError
from pipeline import options as registry


class ProcessingOptionsView(APIView):
    def get(self, request):
        input_type = request.query_params.get("input_type", "point_cloud")
        try:
            applicable = registry.options_for(input_type)
        except registry.UnknownInputTypeError:
            raise ApiError("invalid_input_type") from None

        return Response(
            {
                "input_type": input_type,
                "options": [
                    {
                        "id": opt.id,
                        "label_key": opt.label_key,
                        "description_key": opt.description_key,
                        "target_view": opt.target_view,
                        "required": opt.required,
                        "default_selected": opt.default_selected,
                        "prerequisites": list(opt.prerequisites),
                    }
                    for opt in applicable
                ],
            }
        )
