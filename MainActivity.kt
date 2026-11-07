package com.ssinflu.ai

import android.app.Activity
import android.os.Bundle
import android.content.Intent
import android.graphics.Color
import android.widget.*
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDate
import kotlin.concurrent.thread
import kotlin.math.ln
import kotlin.math.pow

class MainActivity : Activity() {
    private var games = listOf<Game>()
    private lateinit var status: TextView
    private lateinit var home: EditText
    private lateinit var away: EditText
    private lateinit var output: TextView
    private lateinit var urlInput: EditText
    private val picker = 101

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(28, 36, 28, 24); setBackgroundColor(Color.rgb(246,248,252)) }
        fun label(s: String, size: Float = 17f) = TextView(this).apply { text=s; textSize=size; setTextColor(Color.rgb(22,36,58)); setPadding(0,12,0,12) }
        root.addView(label("SSI NFL AI", 28f))
        root.addView(label("Elo • хронологическая проверка • версия 0.4", 15f))
        status=label("Импортируйте CSV завершённых матчей")
        root.addView(status)
        root.addView(Button(this).apply { text="Импортировать CSV с телефона"; setOnClickListener { startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply { type="*/*"; addCategory(Intent.CATEGORY_OPENABLE) }, picker) } })
        urlInput=EditText(this).apply { hint="HTTPS-ссылка на CSV"; setSingleLine(); setText("https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv") }
        root.addView(urlInput)
        root.addView(Button(this).apply { text="Загрузить CSV из интернета"; setOnClickListener { downloadCsv() } })
        root.addView(Button(this).apply { text="Проверить точность на прошлых матчах"; setOnClickListener { backtest() } })
        home=EditText(this).apply { hint="Команда дома (как в CSV)"; setSingleLine() }
        away=EditText(this).apply { hint="Команда в гостях (как в CSV)"; setSingleLine() }
        root.addView(home); root.addView(away)
        root.addView(Button(this).apply { text="Рассчитать прогноз"; setOnClickListener { predict() } })
        output=label("Загрузите результаты nflverse или CSV. Прогноз не гарантирует исход.")
        root.addView(output)
        val scroll=ScrollView(this); scroll.addView(root); setContentView(scroll)
    }

    @Deprecated("Legacy activity result for compatibility")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode,resultCode,data)
        if(requestCode!=picker || resultCode!=RESULT_OK) return
        try { val uri=data?.data ?: return; contentResolver.openInputStream(uri)?.use { load(it) } }
        catch(e:Exception) { status.text="Ошибка импорта: ${e.message}" }
    }

    private fun downloadCsv() {
        val address=urlInput.text.toString().trim()
        if(!address.startsWith("https://")) { status.text="Нужна ссылка HTTPS"; return }
        status.text="Загрузка..."
        thread {
            try {
                val connection=URL(address).openConnection() as HttpURLConnection
                connection.connectTimeout=12000; connection.readTimeout=15000
                connection.instanceFollowRedirects=true
                try {
                    require(connection.responseCode==200) { "HTTP ${connection.responseCode}" }
                    val bytes=connection.inputStream.use { it.readNBytes(15_000_001) }
                    require(bytes.size<=15_000_000) { "CSV больше 15 МБ" }
                    val parsed=parseGames(bytes.inputStream())
                    runOnUiThread { setGames(parsed) }
                } finally { connection.disconnect() }
            } catch(e:Exception) { runOnUiThread { status.text="Ошибка загрузки: ${e.message}" } }
        }
    }

    private fun load(stream:InputStream) { setGames(parseGames(stream)) }
    private fun setGames(parsed:List<Game>) {
        games=parsed
        status.text="Загружено ${games.size} матчей. ${if(games.all { it.date!=null }) "Отсортировано по датам." else "Нет дат: используется порядок строк CSV (старые → новые)."}"
    }
    private fun parseGames(stream:InputStream):List<Game> {
        val lines=stream.bufferedReader(Charsets.UTF_8).use { it.readLines() }
        require(lines.isNotEmpty()) { "CSV пуст" }
        val header=parseCsv(lines.first().removePrefix("\uFEFF")).map { it.trim().lowercase() }
        fun index(vararg aliases:String)=header.indexOfFirst { it in aliases }
        val h=index("home_team","home"); val a=index("away_team","away")
        val hs=index("home_score","home_points"); val ascore=index("away_score","away_points")
        val d=index("date","game_date","gameday")
        require(listOf(h,a,hs,ascore).all { it>=0 }) { "Нужны home_team,away_team,home_score,away_score" }
        val parsed=lines.drop(1).mapNotNull { line ->
            val cols=parseCsv(line)
            if(cols.size<=listOf(h,a,hs,ascore).maxOrNull()!!) null else {
                val x=cols[hs].trim().toIntOrNull(); val y=cols[ascore].trim().toIntOrNull()
                val date=if(d>=0 && d<cols.size) try { LocalDate.parse(cols[d].trim().take(10)) } catch(_:Exception) { null } else null
                if(x==null||y==null||x<0||y<0||cols[h].isBlank()||cols[a].isBlank()||cols[h].trim()==cols[a].trim()) null
                else Game(cols[h].trim(),cols[a].trim(),x,y,date)
            }
        }
        require(parsed.isNotEmpty()) { "Нет корректных завершённых матчей" }
        require(d<0 || parsed.all { it.date!=null }) { "Некорректные даты: ожидается YYYY-MM-DD" }
        return if(d>=0) parsed.sortedBy { it.date } else parsed
    }
    private fun backtest() {
        if(games.size<30) { output.text="Для проверки нужно хотя бы 30 завершённых матчей"; return }
        val stats=Backtest.run(games)
        output.text="Тест без утечки будущих результатов\nПроверено: ${stats.count} матчей с победителем (после 20 стартовых)\nВерных выборов: ${stats.correct} (${"%.1f".format(stats.accuracy*100)}%)\nBrier: ${"%.4f".format(stats.brier)} (меньше лучше)\nLog loss: ${"%.4f".format(stats.logLoss)} (меньше лучше)\nНичьи не считаются верным выбором победителя.\nЭто историческая оценка, не гарантия будущей точности."
    }
    private fun predict() {
        if(games.isEmpty()) { output.text="Сначала импортируйте CSV"; return }
        val h=home.text.toString().trim(); val a=away.text.toString().trim()
        if(h.isEmpty()||a.isEmpty()||h==a) { output.text="Введите две разные команды"; return }
        val model=EloModel(); games.forEach { model.observe(it) }
        val p=model.homeWinProbability(h,a)
        output.text="Победа $h: ${"%.1f".format(p*100)}%\nПобеда $a: ${"%.1f".format((1-p)*100)}%\nВероятности Elo без отдельной модели ничьих и калибровки."
    }
    private fun parseCsv(line:String):List<String> {
        val out=mutableListOf<String>(); val current=StringBuilder(); var quoted=false; var i=0
        while(i<line.length) { val c=line[i]; when { c=='"' && quoted && i+1<line.length && line[i+1]=='"' -> { current.append('"'); i++ }; c=='"' -> quoted=!quoted; c==',' && !quoted -> {out.add(current.toString());current.clear()}; else -> current.append(c) }; i++ }
        out.add(current.toString()); return out
    }
}

data class Game(val home:String,val away:String,val homeScore:Int,val awayScore:Int,val date:LocalDate?=null)
class EloModel {
    private val ratings=mutableMapOf<String,Double>()
    private fun rating(team:String)=ratings[team] ?: 1500.0
    fun homeWinProbability(home:String,away:String):Double = 1.0/(1.0+10.0.pow((rating(away)-rating(home)-55.0)/400.0))
    fun observe(game:Game) {
        val p=homeWinProbability(game.home,game.away)
        val outcome=when { game.homeScore>game.awayScore -> 1.0; game.homeScore<game.awayScore -> 0.0; else -> 0.5 }
        val delta=20.0*(outcome-p)
        ratings[game.home]=rating(game.home)+delta
        ratings[game.away]=rating(game.away)-delta
    }
}
data class TestStats(val count:Int,val correct:Int,val accuracy:Double,val brier:Double,val logLoss:Double)
object Backtest {
    fun run(games:List<Game>, warmup:Int=20):TestStats {
        require(games.size>warmup)
        val model=EloModel(); var n=0; var correct=0; var brier=0.0; var logLoss=0.0
        // Predict all games on the same date before updating any ratings.
        val ordered=games.withIndex().toList()
        val groups=ordered.groupBy { it.value.date ?: LocalDate.MIN.plusDays(it.index.toLong()) }
        for ((_, group) in groups) {
            val predictions=group.map { (index,g) -> Triple(index,g,model.homeWinProbability(g.home,g.away).coerceIn(1e-9,1-1e-9)) }
            for ((index,g,p) in predictions) {
                if (index<warmup || g.homeScore==g.awayScore) continue
                val y=if(g.homeScore>g.awayScore) 1.0 else 0.0
                if ((p>0.5 && y==1.0)||(p<0.5 && y==0.0)) correct++
                brier+=(p-y)*(p-y)
                logLoss+=-(y*ln(p)+(1-y)*ln(1-p))
                n++
            }
            group.forEach { model.observe(it.value) }
        }
        require(n>0) { "Нет матчей с победителем для проверки" }
        return TestStats(n,correct,correct.toDouble()/n,brier/n,logLoss/n)
    }
}
