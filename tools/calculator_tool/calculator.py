class TradeCostCalculator:

    @staticmethod
    def round_value(value):

        return round(value, 2)

    def calculate_import_cost(

        self,
        product_cost,
        quantity,
        shipping_cost,
        insurance_cost,
        customs_duty_percent,
        gst_percent,
        additional_tax_percent=0,
        port_charges=0,
        handling_charges=0,
        miscellaneous_charges=0
    ):

        if quantity <= 0:

            raise ValueError(
                "Quantity must be greater than 0"
            )

        total_product_cost = (
            product_cost * quantity
        )

        cif_value = (

            total_product_cost
            + shipping_cost
            + insurance_cost
        )

        customs_duty = (

            cif_value
            * customs_duty_percent
            / 100
        )

        taxable_value = (
            cif_value + customs_duty
        )

        gst_amount = (

            taxable_value
            * gst_percent
            / 100
        )

        additional_tax = (

            taxable_value
            * additional_tax_percent
            / 100
        )

        final_landed_cost = (

            total_product_cost

            + shipping_cost

            + insurance_cost

            + customs_duty

            + gst_amount

            + additional_tax

            + port_charges

            + handling_charges

            + miscellaneous_charges
        )

        cost_per_unit = (
            final_landed_cost / quantity
        )

        return {

            "trade_type": "import",

            "product_cost":
                self.round_value(
                    total_product_cost
                ),

            "shipping_cost":
                self.round_value(
                    shipping_cost
                ),

            "insurance_cost":
                self.round_value(
                    insurance_cost
                ),

            "cif_value":
                self.round_value(
                    cif_value
                ),

            "customs_duty":
                self.round_value(
                    customs_duty
                ),

            "gst_amount":
                self.round_value(
                    gst_amount
                ),

            "additional_tax":
                self.round_value(
                    additional_tax
                ),

            "port_charges":
                self.round_value(
                    port_charges
                ),

            "handling_charges":
                self.round_value(
                    handling_charges
                ),

            "miscellaneous_charges":
                self.round_value(
                    miscellaneous_charges
                ),

            "final_landed_cost":
                self.round_value(
                    final_landed_cost
                ),

            "cost_per_unit":
                self.round_value(
                    cost_per_unit
                )
        }

    def calculate_export_cost(

        self,
        product_cost,
        quantity,
        packaging_cost,
        shipping_cost,
        insurance_cost,
        export_duty_percent=0,
        gst_refund_percent=0,
        documentation_charges=0,
        logistics_charges=0,
        warehouse_charges=0,
        miscellaneous_charges=0
    ):

        if quantity <= 0:

            raise ValueError(
                "Quantity must be greater than 0"
            )

        total_product_cost = (
            product_cost * quantity
        )

        export_duty = (

            total_product_cost
            * export_duty_percent
            / 100
        )

        gst_refund = (

            total_product_cost
            * gst_refund_percent
            / 100
        )

        final_export_cost = (

            total_product_cost

            + packaging_cost

            + shipping_cost

            + insurance_cost

            + export_duty

            + documentation_charges

            + logistics_charges

            + warehouse_charges

            + miscellaneous_charges

            - gst_refund
        )

        cost_per_unit = (
            final_export_cost / quantity
        )

        return {

            "trade_type": "export",

            "product_cost":
                self.round_value(
                    total_product_cost
                ),

            "packaging_cost":
                self.round_value(
                    packaging_cost
                ),

            "shipping_cost":
                self.round_value(
                    shipping_cost
                ),

            "insurance_cost":
                self.round_value(
                    insurance_cost
                ),

            "export_duty":
                self.round_value(
                    export_duty
                ),

            "gst_refund":
                self.round_value(
                    gst_refund
                ),

            "documentation_charges":
                self.round_value(
                    documentation_charges
                ),

            "logistics_charges":
                self.round_value(
                    logistics_charges
                ),

            "warehouse_charges":
                self.round_value(
                    warehouse_charges
                ),

            "miscellaneous_charges":
                self.round_value(
                    miscellaneous_charges
                ),

            "final_export_cost":
                self.round_value(
                    final_export_cost
                ),

            "cost_per_unit":
                self.round_value(
                    cost_per_unit
                )
        }

    def calculate_profit_margin(

        self,
        selling_price,
        total_cost
    ):

        if selling_price <= 0:

            raise ValueError(
                "Selling price must be greater than 0"
            )

        profit = (
            selling_price - total_cost
        )

        profit_margin_percent = (

            profit
            / selling_price
            * 100
        )

        return {

            "selling_price":
                self.round_value(
                    selling_price
                ),

            "total_cost":
                self.round_value(
                    total_cost
                ),

            "profit":
                self.round_value(
                    profit
                ),

            "profit_margin_percent":
                self.round_value(
                    profit_margin_percent
                )
        }