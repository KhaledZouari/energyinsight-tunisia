let
    Source = MySQL.Database("127.0.0.1:3306", "energyinsight_db", [ReturnSingleDatabase=true, CreateNavigationProperties=false]),
    Monthly = Table.Buffer(Source{[Schema="energyinsight_db",Item="monthly_electricity_consumption"]}[Data]),
    Typed = Table.TransformColumnTypes(Monthly, {
        {"month", type date}, {"total_consumption", type number}, {"invoice_count", Int64.Type},
        {"average_consumption_per_invoice", type number}
    })
in
    Typed
