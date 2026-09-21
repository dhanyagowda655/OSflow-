import numpy as np

try:
    from sklearn.ensemble import GradientBoostingRegressor
    _SKLEARN_AVAILABLE = True
except Exception:
    _SKLEARN_AVAILABLE = False

class DelayPredictor:
    """
    Predicts turnaround delay risk for enterprise requests using historical features:
    - request type (leave, laptop, it_ticket, expense, onboarding, custom)
    - priority (low, medium, high, urgent)
    - step count in workflow
    - department load
    """
    
    TYPE_MAP = {'leave': 0, 'laptop': 1, 'it_ticket': 2, 'expense': 3, 'onboarding': 4, 'custom': 5}
    PRIORITY_MAP = {'low': 0, 'medium': 1, 'high': 2, 'urgent': 3}

    def __init__(self):
        self.model = None
        self._is_trained = False
        self._init_baseline_model()

    def _init_baseline_model(self):
        if _SKLEARN_AVAILABLE:
            try:
                # Seed synthetic baseline data representing typical SLA hours
                # Features: [type_code, priority_code, step_count, pending_queue_depth]
                X = [
                    [0, 1, 3, 2],  # leave, med -> ~4h
                    [0, 2, 3, 5],  # leave, high -> ~2h
                    [1, 1, 5, 8],  # laptop, med -> ~36h
                    [1, 3, 5, 12], # laptop, urgent -> ~18h
                    [2, 0, 2, 10], # it_ticket, low -> ~16h
                    [2, 3, 2, 2],  # it_ticket, urgent -> ~1.5h
                    [3, 1, 4, 6],  # expense, med -> ~24h
                    [4, 1, 7, 3],  # onboarding, med -> ~48h
                    [5, 1, 4, 4],  # custom, med -> ~12h
                ]
                y = [4.0, 2.0, 36.0, 18.0, 16.0, 1.5, 24.0, 48.0, 12.0]
                
                self.model = GradientBoostingRegressor(n_estimators=30, max_depth=3, random_state=42)
                self.model.fit(X, y)
                self._is_trained = True
            except Exception:
                self._is_trained = False

    def predict_delay(self, req_type: str, priority: str = 'medium', step_count: int = 3, queue_depth: int = 2) -> dict:
        """
        Returns predicted turnaround in hours and risk level ('low', 'medium', 'high').
        """
        t_code = self.TYPE_MAP.get((req_type or 'custom').lower(), 5)
        p_code = self.PRIORITY_MAP.get((priority or 'medium').lower(), 1)
        steps = max(1, int(step_count or 3))
        q_depth = max(0, int(queue_depth or 2))

        predicted_hours = 8.0 # Default baseline

        if self._is_trained and self.model is not None:
            try:
                pred = self.model.predict([[t_code, p_code, steps, q_depth]])
                predicted_hours = max(0.5, float(pred[0]))
            except Exception:
                predicted_hours = self._statistical_fallback(t_code, p_code, steps, q_depth)
        else:
            predicted_hours = self._statistical_fallback(t_code, p_code, steps, q_depth)

        if predicted_hours <= 6.0:
            risk = "Low Risk"
            badge = "success"
        elif predicted_hours <= 24.0:
            risk = "Medium Risk"
            badge = "warning"
        else:
            risk = "High Risk"
            badge = "danger"

        return {
            'predicted_hours': round(predicted_hours, 1),
            'risk_level': risk,
            'badge_class': badge,
            'sla_target': f"{round(predicted_hours, 1)} hrs"
        }

    def _statistical_fallback(self, t_code: int, p_code: int, steps: int, q_depth: int) -> float:
        base_hours = {0: 4.0, 1: 32.0, 2: 8.0, 3: 20.0, 4: 40.0, 5: 12.0}.get(t_code, 10.0)
        p_multiplier = {0: 1.4, 1: 1.0, 2: 0.7, 3: 0.4}.get(p_code, 1.0)
        return max(1.0, (base_hours + (steps * 1.5) + (q_depth * 0.8)) * p_multiplier)

delay_predictor = DelayPredictor()
