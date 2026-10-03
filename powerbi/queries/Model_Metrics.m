let
    Source = MySQL.Database("127.0.0.1:3306", "energyinsight_db", [ReturnSingleDatabase=true, CreateNavigationProperties=false]),
    Metrics = Table.Buffer(Source{[Schema="energyinsight_db",Item="model_metrics"]}[Data]),
    TestOnly = Table.SelectRows(Metrics, each [evaluation_set] = "test"),
    Validated = if Table.RowCount(TestOnly) <> 1 then error "Une ligne de métriques test est attendue" else TestOnly,
    Typed = Table.TransformColumnTypes(Validated, {
        {"accuracy", type number}, {"precision", type number}, {"recall", type number},
        {"f1_score", type number}, {"roc_auc", type number}, {"average_precision", type number},
        {"threshold", type number}, {"tn", Int64.Type}, {"fp", Int64.Type}, {"fn", Int64.Type}, {"tp", Int64.Type},
        {"model", type text}, {"evaluation_set", type text}
    })
in
    Typed
