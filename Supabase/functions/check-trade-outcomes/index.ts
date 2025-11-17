// supabase/functions/check-trade-outcomes/index.ts
import { serve } from "https://deno.land/std@0.177.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

interface TradeRecommendation {
  id: string
  symbol: string
  pattern_name: string
  recommendation_direction: string
  virtual_entry: number
  virtual_tp1: number
  virtual_sl: number
  current_price: number
  created_at: string
  status: string
}

serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    // Create Supabase client
    const supabaseClient = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    )

    // Get all pending trade recommendations that are less than 45 minutes old
    const fortyFiveMinutesAgo = new Date(Date.now() - 45 * 60 * 1000).toISOString()
    
    const { data: pendingTrades, error } = await supabaseClient
      .from('trade_recommendations')
      .select('*')
      .eq('status', 'PENDING')
      .gte('created_at', fortyFiveMinutesAgo)
      .order('created_at', { ascending: true })

    if (error) {
      throw error
    }

    console.log(`📊 Processing ${pendingTrades?.length || 0} pending trades`)

    let processedCount = 0

    // Process each pending trade
    for (const trade of pendingTrades || []) {
      try {
        const outcome = await checkTradeOutcome(trade, supabaseClient)
        if (outcome) {
          processedCount++
        }
      } catch (tradeError) {
        console.error(`❌ Error processing trade ${trade.id}:`, tradeError)
      }
    }

    return new Response(
      JSON.stringify({
        message: `Successfully processed ${processedCount} trades`,
        total_pending: pendingTrades?.length || 0
      }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 200,
      }
    )

  } catch (error) {
    console.error('❌ Function error:', error)
    return new Response(
      JSON.stringify({ error: error.message }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 500,
      }
    )
  }
})

async function checkTradeOutcome(trade: TradeRecommendation, supabaseClient: any) {
  try {
    // Get current price from Yahoo Finance
    const currentPrice = await getCurrentPrice(trade.symbol)
    
    if (!currentPrice) {
      console.log(`⚠️ Could not fetch price for ${trade.symbol}`)
      return false
    }

    console.log(`🔍 Checking ${trade.symbol}: current $${currentPrice}, TP1 $${trade.virtual_tp1}`)

    // Calculate minutes since trade was created
    const tradeTime = new Date(trade.created_at)
    const now = new Date()
    const minutesSinceTrade = Math.floor((now.getTime() - tradeTime.getTime()) / (1000 * 60))

    let outcome = 'LOSS' // Default outcome
    let minutesToWin: number | null = null

    // Check if TP1 was hit (for both LONG and SHORT trades)
    if (trade.recommendation_direction === 'LONG' && currentPrice >= trade.virtual_tp1) {
      outcome = 'WIN'
      minutesToWin = minutesSinceTrade
      console.log(`✅ ${trade.symbol} HIT TP1! WIN in ${minutesToWin} minutes`)
    } else if (trade.recommendation_direction === 'SHORT' && currentPrice <= trade.virtual_tp1) {
      outcome = 'WIN'
      minutesToWin = minutesSinceTrade
      console.log(`✅ ${trade.symbol} HIT TP1! WIN in ${minutesToWin} minutes`)
    } else if (minutesSinceTrade >= 45) {
      // 45 minutes elapsed without hitting TP1 - mark as LOSS
      outcome = 'LOSS'
      console.log(`❌ ${trade.symbol} 45 minutes elapsed - LOSS`)
    } else {
      // Trade still active, not time to decide yet
      console.log(`⏳ ${trade.symbol} still active (${minutesSinceTrade}/45 minutes)`)
      return false
    }

    // Update trade outcome in database
    const { error: updateError } = await supabaseClient
      .from('trade_outcomes')
      .insert({
        recommendation_id: trade.id,
        final_outcome: outcome,
        minutes_to_win: minutesToWin,
        max_price_reached: trade.recommendation_direction === 'LONG' ? currentPrice : null,
        min_price_reached: trade.recommendation_direction === 'SHORT' ? currentPrice : null
      })

    if (updateError) throw updateError

    // Update trade status to COMPLETED
    const { error: statusError } = await supabaseClient
      .from('trade_recommendations')
      .update({ status: 'COMPLETED' })
      .eq('id', trade.id)

    if (statusError) throw statusError

    return true

  } catch (error) {
    console.error(`❌ Error checking outcome for ${trade.symbol}:`, error)
    return false
  }
}

async function getCurrentPrice(symbol: string): Promise<number | null> {
  try {
    // Using Yahoo Finance API (free)
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}`
    
    const response = await fetch(url)
    const data = await response.json()
    
    if (data.chart?.result?.[0]?.meta?.regularMarketPrice) {
      return data.chart.result[0].meta.regularMarketPrice
    }
    
    return null
  } catch (error) {
    console.error(`❌ Error fetching price for ${symbol}:`, error)
    return null
  }
}
