class EngineError(Exception):
    pass


class PublishingBlocked(EngineError):
    pass


class PolicyDenied(EngineError):
    pass


class MissingCredentials(EngineError):
    pass


class TermsViolation(EngineError):
    pass


class QuotaExceeded(EngineError):
    pass


class BudgetExceeded(EngineError):
    pass


class IsolationError(EngineError):
    pass


class CadenceCap(EngineError):
    pass


class OneChangeError(EngineError):
    pass


class RepeatTopic(EngineError):
    pass
