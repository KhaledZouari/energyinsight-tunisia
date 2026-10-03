let
    Source = MySQL.Database("127.0.0.1:3306", "energyinsight_db", [ReturnSingleDatabase=true, CreateNavigationProperties=false]),
    Clients = Table.Buffer(Source{[Schema="energyinsight_db",Item="vw_client_risk_analysis"]}[Data]),
    Typed = Table.TransformColumnTypes(Clients, {
        {"client_id", type text}, {"district", type text}, {"region", type text}, {"client_catg", type text},
        {"creation_date", type date}, {"first_invoice_date", type date}, {"last_invoice_date", type date},
        {"target", Int64.Type}, {"actual_target", Int64.Type}, {"predicted_target", Int64.Type},
        {"a_facture_electrique", type logical}, {"anomaly_probability", type number},
        {"probabilite_anomalie", type number}, {"seuil", type number}, {"prediction", Int64.Type},
        {"risk_level", type text}, {"jeu", type text}
    })
in
    Typed
