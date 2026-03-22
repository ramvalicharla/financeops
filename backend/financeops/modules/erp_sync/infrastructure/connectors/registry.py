from __future__ import annotations

from financeops.modules.erp_sync.domain.enums import ConnectorType
from financeops.modules.erp_sync.infrastructure.connectors.aa_framework import AaFrameworkConnector
from financeops.modules.erp_sync.infrastructure.connectors.base import AbstractConnector
from financeops.modules.erp_sync.infrastructure.connectors.busy import BusyConnector
from financeops.modules.erp_sync.infrastructure.connectors.darwinbox import DarwinboxConnector
from financeops.modules.erp_sync.infrastructure.connectors.dynamics365 import Dynamics365Connector
from financeops.modules.erp_sync.infrastructure.connectors.freshbooks import FreshbooksConnector
from financeops.modules.erp_sync.infrastructure.connectors.generic_file import GenericFileConnector
from financeops.modules.erp_sync.infrastructure.connectors.keka import KekaConnector
from financeops.modules.erp_sync.infrastructure.connectors.marg import MargConnector
from financeops.modules.erp_sync.infrastructure.connectors.munim import MunimConnector
from financeops.modules.erp_sync.infrastructure.connectors.netsuite import NetsuiteConnector
from financeops.modules.erp_sync.infrastructure.connectors.odoo import OdooConnector
from financeops.modules.erp_sync.infrastructure.connectors.oracle import OracleConnector
from financeops.modules.erp_sync.infrastructure.connectors.plaid import PlaidConnector
from financeops.modules.erp_sync.infrastructure.connectors.quickbooks import QuickbooksConnector
from financeops.modules.erp_sync.infrastructure.connectors.razorpay import RazorpayConnector
from financeops.modules.erp_sync.infrastructure.connectors.razorpay_payroll import RazorpayPayrollConnector
from financeops.modules.erp_sync.infrastructure.connectors.sage import SageConnector
from financeops.modules.erp_sync.infrastructure.connectors.sap import SapConnector
from financeops.modules.erp_sync.infrastructure.connectors.stripe import StripeConnector
from financeops.modules.erp_sync.infrastructure.connectors.tally import TallyConnector
from financeops.modules.erp_sync.infrastructure.connectors.wave import WaveConnector
from financeops.modules.erp_sync.infrastructure.connectors.xero import XeroConnector
from financeops.modules.erp_sync.infrastructure.connectors.zoho import ZohoConnector


CONNECTOR_REGISTRY: dict[ConnectorType, type[AbstractConnector]] = {
    ConnectorType.TALLY: TallyConnector,
    ConnectorType.BUSY: BusyConnector,
    ConnectorType.MARG: MargConnector,
    ConnectorType.MUNIM: MunimConnector,
    ConnectorType.ZOHO: ZohoConnector,
    ConnectorType.QUICKBOOKS: QuickbooksConnector,
    ConnectorType.XERO: XeroConnector,
    ConnectorType.FRESHBOOKS: FreshbooksConnector,
    ConnectorType.WAVE: WaveConnector,
    ConnectorType.NETSUITE: NetsuiteConnector,
    ConnectorType.DYNAMICS_365: Dynamics365Connector,
    ConnectorType.SAGE: SageConnector,
    ConnectorType.ODOO: OdooConnector,
    ConnectorType.SAP: SapConnector,
    ConnectorType.ORACLE: OracleConnector,
    ConnectorType.RAZORPAY: RazorpayConnector,
    ConnectorType.STRIPE: StripeConnector,
    ConnectorType.AA_FRAMEWORK: AaFrameworkConnector,
    ConnectorType.PLAID: PlaidConnector,
    ConnectorType.KEKA: KekaConnector,
    ConnectorType.DARWINBOX: DarwinboxConnector,
    ConnectorType.RAZORPAY_PAYROLL: RazorpayPayrollConnector,
    ConnectorType.GENERIC_FILE: GenericFileConnector,
}


def get_connector(connector_type: ConnectorType) -> AbstractConnector:
    cls = CONNECTOR_REGISTRY[connector_type]
    return cls()
