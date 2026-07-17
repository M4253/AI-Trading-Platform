"""REST endpoints for safe, local broker configuration management."""
from fastapi import APIRouter, HTTPException, Request, Response, status

from backend.broker.broker_settings import (
    BrokerConfigurationInput,
    create_broker_configuration,
    delete_broker_configuration,
    list_broker_configurations,
    run_mock_connection_test,
    update_broker_configuration,
)
from backend.security.audit import record_audit_event


router = APIRouter(prefix='/broker-configurations', tags=['broker-settings'])


@router.get('')
def list_configurations():
    return {
        'configurations': list_broker_configurations(),
        'paper_trading_default': True,
        'live_trading_enabled': False,
    }


@router.post('', status_code=status.HTTP_201_CREATED)
def create_configuration(configuration: BrokerConfigurationInput, request: Request):
    try:
        created = create_broker_configuration(configuration)
        record_audit_event(
            'settings_change', 'broker_configuration_created', 'broker_configuration', created['id'],
            request=request, details={'mode': created['mode'], 'broker': created['broker']},
        )
        return created
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.put('/{config_id}')
def update_configuration(config_id: str, configuration: BrokerConfigurationInput, request: Request):
    try:
        updated = update_broker_configuration(config_id, configuration)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if not updated:
        raise HTTPException(status_code=404, detail='Broker configuration not found')
    record_audit_event(
        'settings_change', 'broker_configuration_updated', 'broker_configuration', config_id,
        request=request, details={'mode': updated['mode'], 'broker': updated['broker']},
    )
    return updated


@router.delete('/{config_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_configuration(config_id: str, request: Request) -> Response:
    if not delete_broker_configuration(config_id):
        raise HTTPException(status_code=404, detail='Broker configuration not found')
    record_audit_event('settings_change', 'broker_configuration_deleted', 'broker_configuration', config_id, request=request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/{config_id}/test')
def test_configuration(config_id: str, request: Request):
    result = run_mock_connection_test(config_id)
    if not result:
        raise HTTPException(status_code=404, detail='Broker configuration not found')
    record_audit_event(
        'broker_control', 'mock_connection_test_completed', 'broker_configuration', config_id,
        request=request, details={'test_mode': 'mock', 'status': result['status']},
    )
    return result
