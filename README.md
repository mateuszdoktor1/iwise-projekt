# Adaptacyjny dobór przepływności segmentów wideo

Projekt FIS w Pythonie. Odtwarzacz VOD dobiera jeden z czterech wariantów segmentu za pomocą dwuwejściowego systemu Mamdaniego. Symulator odtwarza skutki decyzji na wspólnych dla wszystkich strategii profilach łącza.

## Uruchomienie

Na komputerze projektu uruchom terminal i wpisz poniższe polecenia.

```sh
cd /Users/mateusz/Coding/Python/iwise
conda activate fuzzy
python main.py
```

Domyślne demo pokazuje siły czterech reguł, centroid, decyzję odtwarzacza i porównanie FIS ze stałymi 2 Mb/s. Polecenie zapisuje wykres `wyniki/przebieg_spadek.png`. Na innym komputerze utwórz najpierw środowisko poleceniem `conda env create -f environment.yml`. Alternatywnie w środowisku wirtualnym Pythona 3.12 użyj `python -m pip install -r requirements.txt`. Sprawdzone wersje to Python 3.12.16, NumPy 2.5.5 i Matplotlib 3.11.2. Demo po instalacji działa offline.

| Polecenie | Wynik |
|---|---|
| `python main.py` lub `python main.py demo` | Uruchamia demo na profilu `spadek`. |
| `python main.py decyzja 4 10` | Wypisuje aktywne reguły dla pomiaru 4 Mb/s i zapasu 10 s. |
| `python main.py profile` | Wymienia nazwy dostępnych profili wbudowanych i własnych. |
| `python main.py dodaj-profil moj-test 0:5 20:1.2 55:4` | Zapisuje własny profil, również na kolejne uruchomienia. |
| `python main.py dodaj-profil moj-test 0:5 20:1.2 55:4 --stale 4` | Zapisuje profil ze stałym wariantem porównawczym 4 Mb/s. |
| `python main.py demo wahania` | Porównuje FIS ze stałymi 2 Mb/s dla wybranego profilu i zapisuje jego wykres. W miejsce `wahania` można wpisać dowolną nazwę z listy. |
| `python main.py demo moj-test --stale 1` | Używa stałego wariantu 1 Mb/s w tym uruchomieniu. |
| `python main.py demo moj-test --wszystkie` | Zestawia FIS z 0,5, 1, 2 i 4 Mb/s w jednej tabeli i jednym PNG. |
| `python main.py analiza` | Porównuje wszystkie profile, także własne. W `wyniki/` odtwarza `porownanie.csv`, wykres zbiorów, przykład agregacji, mapę decyzji i przebieg każdego profilu. |
| `python -m unittest -v` | Sprawdza FIS, bilans czasu odtwarzania, zapis i odczyt profili. |
| `python main.py --help` | Pokazuje spis poleceń. Dopisz `--help` po nazwie polecenia, aby zobaczyć jego argumenty. |

## Własny przebieg na obronie

```sh
python main.py dodaj-profil moj-test 0:5 20:1.2 55:4
python main.py demo moj-test
open wyniki/przebieg_moj-test.png
```

Ostatnia komenda otwiera PNG na macOS. Każdy punkt ma postać `sekunda:Mb/s`. W tym przykładzie łącze ma 5 Mb/s od początku, 1,2 Mb/s od 20. sekundy i 4 Mb/s od 55. sekundy do końca. Wystarczy jeden punkt dla stałego łącza. Pierwszy czas wynosi 0, kolejne czasy muszą rosnąć, a prędkości muszą być dodatnie. W punktach profilu działają zarówno `1.2`, jak i `1,2`. Nazwę zacznij literą lub cyfrą, a słowa połącz łącznikiem lub podkreśleniem. Program zapisuje plik `profile/moj-test.txt` i wyświetla polecenie do demo. Aby powtórzyć pokaz, uruchom samo `demo moj-test`. Jeśli chcesz zachować kolejny przebieg, wybierz dla niego inną nazwę.

Opcja `--stale` ustala stałą przepływność filmu używaną do porównania z FIS. Dostępne warianty to 0,5, 1, 2 i 4 Mb/s. Domyślnie profil używa 2 Mb/s. W `dodaj-profil` podana wartość zapisuje się w profilu i obowiązuje przy `demo` oraz `analiza`. Opcja w `demo` ma pierwszeństwo na czas jednego uruchomienia. Program oznacza wybrany wariant w tabeli i na wykresie.

Aby pokazać wszystkie warianty na jednym obrazku, uruchom `python main.py demo spadek --wszystkie` i otwórz `wyniki/porownanie_spadek.png`. W miejsce `spadek` możesz wpisać nazwę własnego profilu. Górny panel przedstawia łącze, cztery środkowe porównują stan bufora FIS z poszczególnymi wariantami stałymi, a dolny pokazuje decyzje FIS. Na wszystkich panelach obowiązuje wspólna skala czasu.

## Jak czytać terminal i wykres

**Pojedyncza decyzja.** Początek każdego demo pokazuje ten sam przykład dydaktyczny (4 Mb/s, 10 s bufora). Liczba po słowie „siła” mówi, w jakim stopniu działa dana reguła. Cztery reguły o sile 0,25 wskazują środki 2, 2, 2 i 4 Mb/s. Środek ciężkości po agregacji wynosi 2,5 Mb/s. Największy dostępny wariant do tej wartości to 2 Mb/s. Gdy prowadząca poda własną parę wejść, użyj `decyzja`. Przykładowo `python main.py decyzja 6 4` daje 1 Mb/s, a `python main.py decyzja 6 12` daje 4 Mb/s. Zmienia się wyłącznie zapas filmu.

**Symulacja filmu.** Każdy wiersz to jedna strategia na całym wybranym profilu. `Start [s]` mierzy czas pobrania pierwszego segmentu. `Zatrzymania [s]` sumują sekundy przerw po uruchomieniu odtwarzania. `Średnia [Mb/s]` dotyczy wybranych wariantów wideo, a `Zmiany` liczą przełączenia wariantu między kolejnymi segmentami. Najpierw porównaj zatrzymania, następnie sprawdź, jaką przepływność i stabilność uzyskano.

Dla powyższego `moj-test` start obu strategii trwa 0,40 s. FIS osiąga 0 s zatrzymań i średnio 1,89 Mb/s przy pięciu zmianach. Przy stałych 2 Mb/s średnia wynosi 1,97 Mb/s, a film stoi łącznie 1,33 s. Jedyna zmiana wynika z przejścia ze wspólnego segmentu startowego 0,5 Mb/s na 2 Mb/s. Wartości w terminalu są zaokrąglone do dwóch miejsc. Po poleceniu `analiza` CSV zawiera wartości o pełnej precyzji.

**Wykres.** Górny panel pokazuje przebieg łącza i ostatnie pomiary dostępne FIS. W środkowym porównaj zapas bufora FIS i strategii stałej. Czerwone pola oznaczają zatrzymania strategii stałej. Dolny panel pokazuje wybrany przez FIS wariant przy zamawianiu kolejnych segmentów.

## Model i źródła wiedzy

W [fis.py](fis.py) zdefiniowano dziewięć reguł. Wejściem jest rozmiar poprzedniego segmentu w megabitach podzielony przez czas pobierania oraz zapas pobranego filmu przed kolejnym żądaniem. Rekomendacja steruje rozmiarem następnego pobrania. Dobór wejść opiera się na praktyce adaptacyjnego streamingu. Progi, macierz reguł, szerokości zbiorów i scenariusze są założeniami projektu. [DASH Industry Forum](https://dashif.org/dash.js/pages/usage/abr/) · [Rahman, Hossain i Huh, 2021](https://doi.org/10.3390/app11115270)

| Zmienna | Jednostka i dziedzina | Zbiory i wierzchołki |
|---|---|---|
| Oszacowana przepustowość | Mb/s, 0–8, nasycenie powyżej 8 | Niska trapez (0,0,1,3), średnia trójkąt (1,3,5), wysoka trapez (3,5,8,8). |
| Zapas w chwili decyzji | s, 0–16 | Mały trapez (0,0,4,8), średni trójkąt (4,8,12), duży trapez (8,12,16,16). |
| Rekomendowana przepływność | Mb/s, oś zbiorów 0,25–4,25, osiągalny centroid 0,5–4 | Niska, umiarkowana, wysoka i bardzo wysoka. Symetryczne trójkąty o środkach 0,5 / 1 / 2 / 4 i połowie szerokości 0,25 Mb/s. |

Iloczyn łączy przesłanki, siła reguły skaluje trójkąt, a suma scala konsekwencje. Przesłanki zawierają wyłącznie AND. Wagi dziewięciu reguł sumują się do jedności. Wyostrzanie przez centroid wykorzystuje całkowanie trapezami w NumPy. Symetria i równe pola trójkątów pozwalają sprawdzić centroid niezależnie jako średnią ważoną środków. Wariant odtwarzacza jest największą dostępną wartością poniżej rekomendacji lub jej równą. Minimum wynosi 0,5 Mb/s. Przykładowo dla wejść (4, 10) środki 2, 2, 2 i 4 mają wagi po 0,25. Centroid wynosi 2,5 Mb/s, a wybrany wariant 2 Mb/s. [Operatory systemu Mamdaniego](https://www.mathworks.com/help/fuzzy/mamfis.html)

## Dane i interpretacja wyników

Trzy profile wbudowane to jawne dane syntetyczne w `PROFILES` w [simulation.py](simulation.py). Dodatkowe przebiegi pochodzą z plików zapisanych przez użytkownika w katalogu `profile/`. Czas jest liczony od pierwszego żądania. Ostatnia wartość łącza obowiązuje do końca filmu. Profil stabilny utrzymuje 6 Mb/s. W scenariuszu spadku łącze zmienia się z 6 na 0,8 Mb/s w 37. sekundzie i wraca do 6 Mb/s w 82. sekundzie. Wahania zmieniają przepustowość między 2,4 a 3,2 Mb/s co 9 s przez zdefiniowany profil.

Film trwa 180 s (45 segmentów po 4 s). Pierwszy segment zawsze ma 0,5 Mb/s. Rozmiar [Mb] to przepływność wariantu [Mb/s] razy 4 s. Zmiana przepustowości w trakcie pobierania wpływa na pozostałą część transferu. Odtwarzanie zaczyna się po pierwszym pobraniu. Przed kolejnym żądaniem symulator czeka, aż w buforze zostanie co najwyżej 16 s. Po dostarczeniu segmentu mieści się w nim do 20 s. Pomiar wykorzystuje wyłącznie czas transferu. Strategia otrzymuje wyłącznie ostatni pomiar i bieżący bufor.

Strategia stała wybiera ustawioną przepływność od drugiego segmentu. Domyślnie jest to 2 Mb/s. Obie strategie pobierają ten sam film na tej samej osi czasu sieci.

Przy spadku łącza FIS uzyskał 0 s zatrzymań, a strategia stała 13,67 s. Przy wahaniach obie strategie osiągnęły 0 s zatrzymań. Strategia stała utrzymała wtedy wyższą średnią przepływność (1,97 wobec 1,38 Mb/s) z jedną zmianą wariantu wobec 18 dla FIS. Zestawienie obejmuje też czas startu. [Porównanie strategii](wyniki/porownanie.csv)

Wnioski dotyczą porównania FIS ze stałymi 2 Mb/s na tych profilach. Model przedstawia pojedynczego klienta, nominalne rozmiary segmentów i natychmiastowe wznowienie po dostarczeniu segmentu. Dalsza walidacja wymagałaby zmierzonych śladów sieci i rzeczywistych wielkości segmentów.

## Prezentacja

Prezentacja ma 14 slajdów. Notatki zawierają proponowany czas, interpretację wykresów i scenariusz demo. Przed oddaniem wpiszcie nazwiska i faktyczny podział pracy na pierwszym i ostatnim slajdzie. [Prezentacja PPTX](prezentacja.pptx)

Na slajdzie 8 przejdź do terminala z aktywnym środowiskiem `fuzzy`.

```sh
python main.py decyzja 6 4
python main.py decyzja 6 12
python main.py demo spadek --wszystkie
```

Przy tym samym pomiarze 6 Mb/s FIS wybiera 1 Mb/s, gdy bufor ma 4 s, oraz 4 Mb/s, gdy ma 12 s. Ostatnie polecenie porównuje pięć strategii na jednym profilu. Wróć na slajd 9, żeby pokazać, że po spadku w 37. sekundzie FIS obniża wariant do 0,5 Mb/s w 52. sekundzie, po zakończeniu pobierania. Na slajdzie 10 widać, że stałe 0,5 i 1 Mb/s również nie powodują zatrzymań, a FIS osiąga od nich wyższą średnią przepływność. [Wykres czterech wariantów](wyniki/porownanie_spadek.png)
