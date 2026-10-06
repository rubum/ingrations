from pathlib import Path
from ingrations.compiler import OpenAPICompiler
from ingrations.models import HTTPMethod, ParameterLocation


def test_compile_openapi_dict():
    sample_spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "Payment Gateway API",
            "description": "API for customer transactions and billing",
            "version": "2.1.0"
        },
        "servers": [{"url": "https://api.paymentgateway.com/v1"}],
        "paths": {
            "/charges": {
                "post": {
                    "operationId": "create_charge",
                    "summary": "Create a new charge",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["amount", "currency"],
                                    "properties": {
                                        "amount": {"type": "integer", "description": "Amount in cents"},
                                        "currency": {"type": "string", "default": "usd"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/charges/{charge_id}": {
                "get": {
                    "operationId": "get_charge",
                    "summary": "Retrieve charge by ID",
                    "parameters": [
                        {
                            "name": "charge_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"}
                        }
                    ]
                }
            }
        }
    }

    app_spec = OpenAPICompiler.compile_spec(sample_spec, app_id="paygate")
    assert app_spec.id == "paygate"
    assert app_spec.name == "Payment Gateway API"
    assert app_spec.base_url == "https://api.paymentgateway.com/v1"
    assert len(app_spec.actions) == 2

    # Check create_charge
    create_op = next(a for a in app_spec.actions if a.id == "paygate.create_charge")
    assert create_op.method == HTTPMethod.POST
    param_names = [p.name for p in create_op.parameters]
    assert "amount" in param_names
    assert "currency" in param_names

    # Check get_charge
    get_op = next(a for a in app_spec.actions if a.id == "paygate.get_charge")
    assert get_op.method == HTTPMethod.GET
    path_param = next(p for p in get_op.parameters if p.name == "charge_id")
    assert path_param.location == ParameterLocation.PATH
    assert path_param.required is True


def test_export_compiled_to_catalog(tmp_path: Path):
    sample_spec = {
        "openapi": "3.0.0",
        "info": {"title": "Test Service", "description": "Git repository tool"},
        "paths": {
            "/status": {
                "get": {"operationId": "check_status", "summary": "Check Status"}
            }
        }
    }
    app = OpenAPICompiler.compile_spec(sample_spec, "test_svc")
    out_file = OpenAPICompiler.export_to_catalog(app, tmp_path)
    assert out_file.exists()
    assert "test_svc.json" in out_file.name
