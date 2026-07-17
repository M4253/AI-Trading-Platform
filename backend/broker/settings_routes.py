"""REST endpoints for safe, local broker configuration management."""
from fastapi import APIRouter, HTTPException, Response, status

from backend.broker.broker_settings import (
    BrokerConfigurationInput,
    create_broker_configuration,
    delete_broker_configuration,
    list_broker_configurations,
    run_mock_connection_test,
    update_broker_configuration,
)


router = APIRouter(prefix='/broker-configurations', tags=['broker-settings'])


@router.get('')
def list_configurations():
    return {
        'configurations': list_broker_configurations(),
        'paper_trading_default': True,
        'live_trading_enabled': False,
    }


@router.post('', status_code=status.HTTP_201_CREATED)
def create_configuration(configuration: BrokerConfigurationInput):
    try:
        return create_broker_configuration(configuration)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.put('/{config_id}')
def update_configuration(config_id: str, configuration: BrokerConfigurationInput):
    try:
        updated = update_broker_configuration(config_id, configuration)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if not updated:
        raise HTTPException(status_code=404, detail='Broker configuration not found')
    return updated


@router.delete('/{config_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_configuration(config_id: str) -> Response:
    if not delete_broker_configuration(config_id):
        raise HTTPException(status_code=404, detail='Broker configuration not found')
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/{config_id}/test')
def test_configuration(config_id: str):
    result = run_mock_connection_test(config_id)
    if not result:
        raise HTTPException(status_code=404, detail='Broker configuration not found')
    return result
