"""Composition root for application services used by transport adapters."""

from dataclasses import dataclass
from typing import cast

from flask import Flask, current_app
from sqlalchemy.orm import Session, sessionmaker

from configs import dify_config
from constants.dsl_version import CURRENT_APP_DSL_VERSION
from core.db.session_factory import get_session_maker
from core.schemas.schema_manager import SchemaManager
from enums import DeploymentEdition
from extensions.ext_redis import RedisClientWrapper, redis_client
from libs.datetime_utils import naive_utc_now
from libs.helper import RateLimiter
from repositories.account_integration_repository import SQLAlchemyAccountIntegrationRepository
from repositories.account_repository import SQLAlchemyAccountRepository
from repositories.explore_banner_query_repository import ExploreBannerQueryRepository
from repositories.installation_state_repository import InstallationStateRepository
from repositories.workspace_member_query_repository import WorkspaceMemberQueryRepository
from repositories.workspace_query_repository import WorkspaceQueryRepository
from services.account_avatar_file_gateway import SQLAlchemyAccountAvatarFileGateway
from services.account_avatar_service import AccountAvatarService
from services.account_change_email_adapters import (
    BillingAccountEmailPolicyGateway,
    CeleryChangeEmailNotificationGateway,
    RateLimiterChangeEmailSendLimiter,
    RedisChangeEmailSecurityGateway,
    SecureChangeEmailCodeGenerator,
    TokenManagerChangeEmailTokenGateway,
)
from services.account_change_email_service import AccountChangeEmailService
from services.account_deletion_adapters import (
    CeleryAccountDeletionScheduler,
    CeleryAccountDeletionVerificationNotifier,
    EnterpriseAccountDeletionSyncGateway,
    TokenManagerAccountDeletionVerificationGateway,
)
from services.account_deletion_service import AccountDeletionService
from services.account_initialization_service import AccountInitializationService
from services.account_integration_service import AccountIntegrationService
from services.account_password_hasher import LegacyAccountPasswordHasher
from services.account_password_service import AccountPasswordService
from services.account_profile_service import AccountProfileService
from services.explore_banner_query_service import ExploreBannerQueryService
from services.feature_query_service import FeatureQueryService
from services.feature_service import FeatureService
from services.feature_service_gateway import FeatureServiceGateway
from services.init_validation_service import InitValidationService
from services.schema_definition_service import SchemaDefinitionService
from services.setup_adapters import RedisSetupLock, RegisterServiceAccountProvisioner
from services.setup_service import SetupService
from services.workspace_member_query_service import WorkspaceMemberQueryService
from services.workspace_member_role_resolver import DeploymentWorkspaceMemberRoleResolver
from services.workspace_plan_gateway import DeploymentWorkspacePlanGateway
from services.workspace_query_service import WorkspaceQueryService

_EXTENSION_KEY = "application_services"


@dataclass(frozen=True, slots=True)
class AccountServices:
    avatar: AccountAvatarService
    change_email: AccountChangeEmailService
    deletion: AccountDeletionService
    initialization: AccountInitializationService
    integrations: AccountIntegrationService
    password: AccountPasswordService
    profile: AccountProfileService


@dataclass(frozen=True, slots=True)
class ApplicationServices:
    accounts: AccountServices
    explore_banner_queries: ExploreBannerQueryService
    schema_definitions: SchemaDefinitionService
    setup: SetupService
    feature_queries: FeatureQueryService
    init_validation: InitValidationService
    workspace_queries: WorkspaceQueryService
    workspace_member_queries: WorkspaceMemberQueryService


def build_application_services(
    *,
    database_client: sessionmaker[Session],
    deployment_edition: DeploymentEdition,
    initialization_password: str,
    redis: RedisClientWrapper,
) -> ApplicationServices:
    installation_state = InstallationStateRepository(client=database_client)
    accounts = SQLAlchemyAccountRepository(database_client)
    integrations = SQLAlchemyAccountIntegrationRepository(database_client)
    workspace_query_repository = WorkspaceQueryRepository(client=database_client)
    return ApplicationServices(
        accounts=AccountServices(
            avatar=AccountAvatarService(
                files=SQLAlchemyAccountAvatarFileGateway(session_factory=database_client),
            ),
            change_email=AccountChangeEmailService(
                accounts=accounts,
                tokens=TokenManagerChangeEmailTokenGateway(),
                codes=SecureChangeEmailCodeGenerator(),
                notifications=CeleryChangeEmailNotificationGateway(),
                send_limits=RateLimiterChangeEmailSendLimiter(
                    rate_limiter=RateLimiter(
                        prefix="change_email_rate_limit",
                        max_attempts=1,
                        time_window=60,
                        redis_client=redis,
                    )
                ),
                security=RedisChangeEmailSecurityGateway(
                    redis=redis,
                    email_send_ip_limit_per_minute=dify_config.EMAIL_SEND_IP_LIMIT_PER_MINUTE,
                    verification_failure_limit=5,
                    verification_lockout_duration=dify_config.CHANGE_EMAIL_LOCKOUT_DURATION,
                ),
                email_policy=BillingAccountEmailPolicyGateway(
                    billing_enabled=dify_config.BILLING_ENABLED,
                ),
            ),
            deletion=AccountDeletionService(
                accounts=accounts,
                memberships=workspace_query_repository,
                verification=TokenManagerAccountDeletionVerificationGateway(),
                notifications=CeleryAccountDeletionVerificationNotifier(
                    rate_limiter=RateLimiter(
                        prefix="email_code_account_deletion_rate_limit",
                        max_attempts=1,
                        time_window=60,
                        redis_client=redis,
                    )
                ),
                synchronization=EnterpriseAccountDeletionSyncGateway(),
                scheduler=CeleryAccountDeletionScheduler(),
            ),
            initialization=AccountInitializationService(
                accounts=accounts,
                invitation_required=deployment_edition == DeploymentEdition.CLOUD,
                now=naive_utc_now,
            ),
            integrations=AccountIntegrationService(integrations=integrations),
            password=AccountPasswordService(
                accounts=accounts,
                passwords=LegacyAccountPasswordHasher(),
            ),
            profile=AccountProfileService(accounts=accounts),
        ),
        explore_banner_queries=ExploreBannerQueryService(
            banners=ExploreBannerQueryRepository(client=database_client),
            is_enabled=FeatureService.is_explore_banner_enabled,
        ),
        schema_definitions=SchemaDefinitionService(source_factory=SchemaManager),
        setup=SetupService(
            state=installation_state,
            accounts=RegisterServiceAccountProvisioner(client=database_client),
            lock=RedisSetupLock(client=redis),
            setup_required=deployment_edition != DeploymentEdition.CLOUD,
        ),
        feature_queries=FeatureQueryService(
            features=FeatureServiceGateway(),
            trial_models=FeatureService.get_trial_models(),
            app_dsl_version=CURRENT_APP_DSL_VERSION,
        ),
        init_validation=InitValidationService(
            state=installation_state,
            validation_required=(deployment_edition != DeploymentEdition.CLOUD and bool(initialization_password)),
            expected_password=initialization_password,
        ),
        workspace_queries=WorkspaceQueryService(
            workspaces=workspace_query_repository,
            plans=DeploymentWorkspacePlanGateway(),
        ),
        workspace_member_queries=WorkspaceMemberQueryService(
            members=WorkspaceMemberQueryRepository(
                session_factory=database_client,
            ),
            roles=DeploymentWorkspaceMemberRoleResolver(),
        ),
    )


def init_app(app: Flask) -> None:
    app.extensions[_EXTENSION_KEY] = build_application_services(
        database_client=get_session_maker(),
        deployment_edition=dify_config.DEPLOYMENT_EDITION,
        initialization_password=dify_config.INIT_PASSWORD,
        redis=redis_client,
    )


def application_services() -> ApplicationServices:
    """Return the application services bound to the current Flask app."""
    return cast(ApplicationServices, current_app.extensions[_EXTENSION_KEY])
