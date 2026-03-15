import pytest
from datetime import datetime
from main import VisuraRequest, VisuraIntestatiRequest, VisuraResponse
from pydantic.fields import FieldInfo

def test_visuracenter_models_timestamp():
    # Arrange & Act
    req1 = VisuraRequest(
        request_id="1",
        tipo_catasto="T",
        provincia="RM",
        comune="ROMA",
        foglio="1",
        particella="1"
    )
    req2 = VisuraIntestatiRequest(
        request_id="2",
        tipo_catasto="F",
        provincia="RM",
        comune="ROMA",
        foglio="1",
        particella="1",
        subalterno="1",
    )
    res = VisuraResponse(
        request_id="3",
        success=True,
        tipo_catasto="T"
    )

    # Assert
    assert isinstance(req1.timestamp, datetime), f"Expected datetime, got {type(req1.timestamp)}"
    assert isinstance(req2.timestamp, datetime), f"Expected datetime, got {type(req2.timestamp)}"
    assert isinstance(res.timestamp, datetime), f"Expected datetime, got {type(res.timestamp)}"

    assert not isinstance(req1.timestamp, FieldInfo), "timestamp should not be a Pydantic FieldInfo"
    assert not isinstance(req2.timestamp, FieldInfo), "timestamp should not be a Pydantic FieldInfo"
    assert not isinstance(res.timestamp, FieldInfo), "timestamp should not be a Pydantic FieldInfo"
