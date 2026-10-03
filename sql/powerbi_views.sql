-- Vue attendue par le rapport historique, basée sur les tables finales.
CREATE OR REPLACE VIEW vw_client_risk_analysis AS
SELECT c.*, p.actual_target, p.predicted_target, p.anomaly_probability,
       p.risk_level, p.jeu, p.seuil, p.prediction, p.probabilite_anomalie
FROM client_ml_dataset AS c
LEFT JOIN client_predictions AS p ON c.client_id = p.client_id;
