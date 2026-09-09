# Reading the LibyaData Central Bank series in R.
#
# Demonstrates the two things most likely to be got wrong: the money supply is
# reported in millions of dinars across several exchange-rate regimes, and the
# CPI is not continuous across the 2025 rebasing.

library(stargazer)

processed <- file.path("..", "data", "processed")

m2   <- read.csv(file.path(processed, "cbl_money_supply.csv"))
base <- read.csv(file.path(processed, "cbl_monetary_base.csv"))
fx   <- read.csv(file.path(processed, "cbl_fx_by_bank.csv"))

m2$date   <- as.Date(m2$date)
base$date <- as.Date(base$date)

# --- Money multiplier -------------------------------------------------------
mm <- merge(m2[, c("date", "money_supply_m2")],
            base[, c("date", "monetary_base")], by = "date")
mm$multiplier <- mm$money_supply_m2 / mm$monetary_base
mm$year <- as.integer(format(mm$date, "%Y"))

stargazer(mm[, c("money_supply_m2", "monetary_base", "multiplier")],
          type = "text", digits = 1,
          title = "Libyan monetary aggregates, 2004-2026 (million LYD)")

# --- Currency in circulation as a share of M2 -------------------------------
# Rises sharply after 2014: cash hoarding under the banking-sector liquidity
# crisis is one of the clearer quantitative signatures of the institutional
# split, and is visible directly in the published series.
m2$cash_share <- 100 * m2$currency_in_circulation / m2$money_supply_m2
m2$year <- as.integer(format(m2$date, "%Y"))
annual <- aggregate(cash_share ~ year, data = m2, FUN = mean)
print(annual, row.names = FALSE)

# --- Consumer prices: respect the base break --------------------------------
cpi <- read.csv(file.path(processed, "bsc_cpi_by_group.csv"),
                colClasses = c(group_code = "character"))
general <- cpi[cpi$group_code == "00", ]

# Levels on different bases are not comparable. Compute inflation within each
# base separately, then combine the growth rates.
general <- general[order(general$base_year, general$year, general$month), ]
general$inflation_yoy <- ave(
  general$index, general$base_year,
  FUN = function(x) c(rep(NA, 12), 100 * (x[-seq_len(12)] / head(x, -12) - 1))
)

stargazer(general[, c("index", "inflation_yoy")], type = "text", digits = 1,
          title = "Libyan CPI, general index and year-on-year inflation")

# --- Foreign exchange allocation concentration ------------------------------
# Herfindahl index of bank shares in official foreign exchange purchases.
latest <- fx[fx$period_end == max(fx$period_end), ]
latest <- latest[latest$year == max(latest$year) & !is.na(latest$value_usd), ]
hhi <- sum((100 * latest$value_usd / sum(latest$value_usd))^2)
cat(sprintf("\nHHI of bank shares in FX purchases, %s: %.0f across %d banks\n",
            max(fx$period_end), hhi, nrow(latest)))
