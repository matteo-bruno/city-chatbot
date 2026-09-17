# A universal framework for inclusive 15-minute cities

**Citation:** Bruno, M., Melo, H. P. M., Campanelli, B. & Loreto, V. A universal framework for inclusive 15-minute cities. Nature Cities 1, 633-641 (2024)

**Source:** https://doi.org/10.1038/s44284-024-00119-4

*Extracted from 3ce7c5ba-nature_cities_universal_framework_inclusive_15_minute_cities.pdf, 9 pages.*


## Page 1

Article
A universal framework for inclusive
15-minute cities
Matteo Bruno    1,2 , Hygor Piaget Monteiro Melo    1,2,3,
Bruno Campanelli    1,2,4 & Vittorio Loreto1,2,4,5
Proximity-based cities have attracted much attention in recent years.
The ‘15-minute city’ , in particular, heralded a new vision for cities where
essential services must be easily accessible. Despite its undoubted merit
in stimulating discussion on new organization of cities, the 15-minute
city cannot be applicable everywhere, and its very definition raises a few
concerns. Here we tackle the feasibility and practicability of the 15-minute
city model in many cities worldwide. We provide a worldwide quantification
of how close cities are to the ideal of the 15-minute city. T o this end, we
measure the accessibility times to resources and services, and we reveal
strong heterogeneity of accessibility within and across cities, with a pivotal
role played by local population densities. We provide an online platform
(https://whatif.sonycsl.it/15mincity/) to access and visualize accessibility
scores for virtually all cities worldwide. The heterogeneity of accessibility
within cities is one of the sources of inequality. We thus simulate how
much a better redistribution of resources and services could heal inequity
by keeping the same resources and services or by allowing for virtually
infinite resources. We highlight pronounced discrepancies among cities
in the minimum number of additional services needed to comply with the
15-minute city concept. We conclude that the proximity-based paradigm
must be generalized to work on a wide range of local population densities.
Finally, socio-economic and cultural factors should be included to shift from
time-based to value-based cities.
In the past few years, a strong push for redesigning our urban landscapes emerged to set the stage for a future of more sustainable and
connected urban living. This novel movement took off from the need
for local accessibility to services and reducing carbon emissions from
private transportation.
The recently trending concept of the 15-minute city contends that
cities can function more effectively, equitably and environmentally
if essential services and key amenities are within 15 minutes by nonpolluting forms of transport, such as walking or cycling1. It provides an
alternative to car-dependent urban designs and generally deleterious
long-distance commuting. By focusing on proximity, this approach can
address pressing issues like air pollution, traffic congestion and social
disparities2. The 15-minute city concept also rose in popularity dur -
ing and after the COVID-19 pandemic, as local communities regained
importance and people, even reluctantly, rediscovered the possibility
of enjoying their neighborhood 3, calling for new urban solutions to
enhance walkability4.
The notion of proximity-based cities has been around for a while,
due to decades of increasing interest in compact cities 5,6. The longstanding dualism between suburban cities and compact urban planning
Received: 6 February 2024
Accepted: 2 August 2024
Published online: xx xx xxxx
 Check for updates
1Sony Computer Science Laboratories – Rome, Joint Initiative CREF-SONY, Centro Ricerche Enrico Fermi, Rome, Italy. 2Centro Ricerche Enrico Fermi,
Rome, Italy. 3Instituto Federal de Educação, Ciência e Tecnologia do Ceará, Acaraú, Ceará, Brazil. 4Sapienza University of Rome, Physics Department,
Rome, Italy. 5Complexity Science Hub, Vienna, Austria.  e-mail: matteo.bruno@sony.com


## Page 2

be highly unequal regarding the quality of the services provided or
might lead to a reduction of green areas10. Two areas of the same city
could have perfect 15-minuteness, but one could have top-tier and
the other inferior services, forming a fertile ground for inequality and
segregation. In addition, as we shall see in this Article, local population
density plays a pivotal role in determining the best scenarios for future
cities. The practicality of the 15-minute city still needs to be determined,
as well as its consequential impact on the resident’s quality of life. Some
studies have begun to quantitatively measure the impact and influence
has been at the center of public debate recently due to the need to create sustainable environments and reduce CO2 produced by transport
emissions, which recent studies confirm to be lower in dense cities 7.
Therefore, a new focus on eco-urbanism solutions has arisen, with the
challenge of building more compact cities and improving accessibility8.
Transforming a city into a 15-minute one is a challenging task. It
calls for substantial shifts in urban design, transportation strategies
and land use policies9. Despite its increasing appeal, the 15-minuteness
raises essential concerns. For instance, a perfectly 15-minute city could
Rome
10 km
Paris
15 km
Atlanta
15 km
Tokyo
25 km
Addis Ababa
5 km
Bogotá
5 km
Mexico City
15 km 15 km
Melbourne
0
5
10
15
20
25
30
PT (min)
0 10 20 30 40 50 60
0
20
40
60
80
100
Madrid
Greater Sydney
Osaka
Tokyo
Seoul
Bogotá
Shanghai
Greater Melbourne Hanoi
Santiago
London
São Paulo
Dallas
Mumbai
Paris
Beijing Mexico city
Buenos Aires
Rio de Janeiro
Nairobi
200 inhabitants km –2
1,000 inhabitants km –2
7,000 inhabitants km –2
0.15
0.20
0.25
0.30
0.35
0.40
0.45
0.50
0.55
Gini index of accessibility
10
1
10
2
PT (min)
0
20
40
60
80
100
Cumulative population below time (%)
F15
PT city  (min)
Beijing
Melbourne
Mexico City
Bogotá
Barcelona
Tokyo
Atlanta
Paris
Rome
15 minutes
a
b c
Fig. 1 | Local accessibility measured in several different cities. a, Computed
maps of local accessibility scores for a subset of the studied cities. Each hexagon
in each city is colored according to PT, that is, the time to access the services of
the 15-minute city. The color code is such that blue (red) colors correspond to
areas where the accessibility time of the services is below (above) 15 minutes.
Remarkable differences are observed among different cities. For instance,
a small fraction of the city area in Atlanta has PTs that are less than 15 minutes.
Conversely, Paris has a considerable fraction of the city area below 15 minutes.
b, The cumulative distribution of PT scores among the population in selected
cities, that is, the population fraction whose accessibility is below a given PT.
The curves for different cities display similar S-shaped behaviors, though their
growth occurs at very different positions. We highlight the curve intercept for
a PT of 15 minutes, revealing the fraction of the population living in a 15-minute
condition. c, A scatter plot of different accessibility scores of cities in our study.
For each city, we report the average PT score, PTcity, versus the fraction of the
population living in a 15-minute condition, F15. The circle size is proportional to
the population density of the city (inhabitants per km2). The color codes for the
Gini index, which captures the unequal accessibility across cities. The triangular
gray area represents a theoretically unreachable phase: if a city has a low PTcity,
the proportion of people within 15-minute accessibility cannot be lower than a
certain percentage. We observe a decreasing trend of F15 versus PTcity, which is to be
expected. Less trivial is that the Gini index shows an increasing trend with PTcity.


## Page 3

of such an urban structure11. Moreover, many cities have begun journeys
to improve accessibility and create compact districts12, but there is no
unique recipe for such changes.
Measuring local accessibility to services is a cornerstone in this
exploration. The quest for measuring accessibility began long ago,
and various measures have been employed13–15. All these studies point
out that cities are not homogeneous bodies: it is crucial to acknowl -
edge that not all parts of a city are equal, leading to varying degrees
of accessibility16–20. Thus, previous studies point towards inequality
of access even in 15-minute cities 21,22. Therefore, urban studies have
focused on population landscapes, that is, the distributions of local
population density and how to improve accessibility for the largest
possible fraction of the population. One popular approach is to place
amenities to meet the needs of the population optimally; this complex
problem can be formulated in various ways, and some algorithms have
been proposed. For instance, in ref. 23 the total travel distance of the
population to reach the nearest facility in space is minimized, simulating this allocation at a country level, and in a similar spirit in ref. 24 the
optimization of the facilities is performed at the scale of a single city.
Other previous work includes the use of shape grammar25 and considers
mobility26. Here, we aim to merge these theoretical accessibility designs
with the quest for the 15-minute city to understand how optimally
placed amenities can improve local accessibility in urban contexts.
As a first contribution of the Article, we measure accessibility in
cities worldwide, probing the distribution of services and pinpoint -
ing regions where disparities are the most conspicuous. Further, we
scrutinize the practicality of the 15-minute city by imagining a more
equal distribution of services, considering the spatial distribution
of population densities. We propose a novel algorithmic approach to
create scenarios wherein city services are redistributed based on population distributions. By simulating a hypothetical equal relocation of
services, we can forecast potential enhancements in urban accessibility.
Finally, we employ our algorithm to fine-tune the number of services to
reach an equal 15-minute city condition. Measuring the quantity of per
capita services needed for this goal, we demonstrate that the number
of services required fluctuates remarkably and depends on the population density and how the population is distributed in the territory. We
contend that our analysis can offer insights that can serve as catalysts
for urban planners and decision-makers, fostering the creation of cities
that are more equitable, accessible and sustainable.
Results
Assessing current 15-minuteness
We start our analysis by conducting a thorough assessment of the closeness of current cities to the ideal of 15-minuteness. The first notable
result, extracted from the study of many cities worldwide, is a pretty
substantial heterogeneity of accessibility both within and across different cities. In this Article, we will illustrate more than 50 cities in depth,
and we refer the reader to the online platform that we made freely available, which now covers around 10,000 cities worldwide. For all cities, we
define and measure the so-called proximity time (PT; see ‘ Accessibility
calculation’ for its definition) both locally and for each city as a whole.
PT measures how long it takes from a specific point in the city to reach
the services of the 15-minute city, either by walking or cycling. Figure 1a
reports the maps of PT values (by walking) for some selected cities. The
first striking evidence refers to the differences among different cities.
Equally, remarkable differences are also observed within a single city,
implying that accessibility is not a ‘currency’ equally distributed in the
population, with a centric structure of cities or polycentric one in some
notable cases, for example, Barcelona and Paris. The distribution of all
PT scores of cities worldwide can be found in Supplementary Section 1.
T o quantify the level of inequality in accessibility, we measure, for
each city, the fraction of the population living in a 15-minute condition,
that is, the fraction of residents with access to essential services within
a 15-minute radius. We name this quantity F15. Here essential services are
classified in nine categories: outdoor activities, learning, supplies, eating, moving, cultural activities, physical exercise, services and health
care. This categorization captures most essential daily activities and
allows for both general and category-specific accessibility assessment
(see ‘ Accessibility calculation’). Figure 1b,c shows a quantification of
the inequalities in accessibility within and across cities. Two striking
results emerge. First, there is considerable variation in the fraction of
the population living in a 15-minute condition across different cities
(Fig. 1b). Second (Fig. 1c), within the same city, variations in accessibility can be large, and they tend to grow with average PT score, mean -
ing that cities with bad average accessibility are also more unequal.
Finally, substantial variations exist among cities in different cultural
contexts, mainly based on how car-centric and suburban the urban
planning style is.
Our analysis consistently highlights patterns where city centers
have better access to services than peripheral areas. However, notable
exceptions exist, such as Paris or Barcelona, whose recent policies
on increasing local access to services are well known 12. These cities
exhibit a more evenly distributed accessibility, transcending the typical
center–periphery divide. It is in the nature of cities, however, to provide
more services in their centers: it is the most convenient place for people from different areas to meet, and therefore an attractive place for
offices and shops. But the self-reinforcing process of ‘rich get richer’
has to be avoided: more services mean more people willing or needing
to visit the city centers and an ever-increasing demand for services in
the centers, making the peripheries ever more empty and isolated.
T owards an optimally equal distribution of opportunities
Having assessed the levels of inequality in urban accessibility, it is natural to raise the question of what could be done to mitigate those inequalities. Lacking systematic empirical examples, we could first ask whether
a suitable relocation of the existing points of interest (POIs) could lead
to better accessibility patterns and, on a quantitative ground, to more
of the population living in a 15-minute condition (higher F15 values). T o
this end, we have devised an algorithm that optimally redistributes the
POIs that already exist in a given city. Figure 2a describes the algorithm’s
rationale for redistributing POIs based on the population distribution
within each city. The algorithm aims to have an equal amount of services
per capita, or equivalently per 1,000 people, across the city, leading to
a more balanced distribution of services than the actual distribution. In
this scenario, every amenity will serve an approximately equal amount
of people in its neighborhood.
The application of our algorithm yields some insights when considering how many services need to be relocated to different areas
from their original ones. Figure 2b illustrates that cities known for their
car-centric designs, such as Atlanta and other North American cities,
need to relocate a high percentage of POIs, over 70% in some cases;
conversely, certain European cities, including Milan, Copenhagen,
Lisbon and Paris, already demonstrate a well-optimized, homogeneous distribution of services. Here, the need for relocation is minimal,
reinforcing the effectiveness of the present urban design in making
the city walkable and accessible. These findings highlight the diverse
challenges different cities can face as they strive to improve their accessibility and become 15-minute cities. Figure 2c reports an example of
how the relocation algorithm changes the map of the local number of
POIs per 1,000 people in Rome.
Let us see now how the relocation of POIs affects accessibility
across various cities. We present these shifts in accessibility in Fig. 3
through two distinct visuals. Figure 3a,b shows maps of Rome and
Atlanta with a color code associated with the changes in accessibility
(the PT score) at the local level. By redistributing POIs, we create areas
of positive changes (blueish areas) and negative changes (reddish
areas), whereas some areas are unchanged. It is remarkable how the
city center does not get stripped of services despite the growth in
accessibility of other less central areas. Further, the peripheral regions


## Page 4

Cur r ent scenario (R ome)
 Optimized scenario (R ome)
0 20 40 60 80 100
POIs per 1,000 people
0
0.025
0.050
0.075
0 20 40 60 80 100
POIs per 1,000 people
0
0.01
0.02
0.03
Density
L ocal average weighted by pop ulation
Global average
0
20
Avg ≈ 35
100
200+
POIsper1,000people
15 min
15-min
r eachable
population
Allocation
15 min
Zurich
3.46
Milan
3.62
T urin
4.47
Copenhagen
5.18
Lisbon
8.27
P aris
9.76
Dublin
10.17
Munich
11.11
Athens
11.40
Barcelona
11.48
V ienna
11.56
Sapporo
11.81
Rome12.09
Oslo12.84
Prague
13.36
Berlin
13.96 Helsinki
15.03 Madrid
15.45
Montreal
15.89
W arsaw
16.30
T allinn
16.56
Bogotá
17.53
T okyo
17.57
London
18.68
Budapest
19.48
Osaka
20.28
Seoul
21.83
Amsterdam
22.39
Santiago
23.89
Medellin
25.03
Auckland
26.31
Rotterdam
29.74
F ukuoka
29.77
Edinburgh
31.26
Greater Sydney
32.46
São P
aulo
32.46
F ortaleza
32.79
Greater Melbourne
32.83
Buenos Aires
37.52
Hanoi 37.70
Milwauk ee 38.10
Addis Ababa
38.95Nairobi
43.04
Boston
43.17
Beijing
44.10
Mumbai
44.33
Minneapolis
46.68
Rio de
Janeiro
48.28
Mexico City
53.19
Shanghai
55.98
Detroit (Greater)
59.43
Dallas
70.62
San Antonio
74.65
Atlanta
79.29
Percentage of POIs
to be relocated for equal
POIs per capita
0%
10%
30%
50%
100%
a b
c
Fig. 2 | Algorithmic distribution of POIs. a, Schematic showing the rationale
for the algorithm (see ‘POI relocation algorithm’ for a thorough description):
the more people who are reachable in 15 minutes from a certain area of a city, the
more POIs will be placed there and its surroundings. b, A ranking of the fraction of
POIs relocated in each city after applying the algorithm. A stark variation across
cities is immediately noticeable. c, Two maps of Rome colored according to the
local number of POIs per 1,000 people, equivalent to POIs per capita, calculated
before (left) and after (right) application of the relocation algorithm. Each map
is complemented by a histogram. The algorithm makes the local availability of
services per capita close to the global average in the city.


## Page 5

experience a substantial enhancement in their access to services,
validating the efficiency of the relocation strategy in bridging accessibility disparities. Reddish areas get worse in accessibility, presumably
because they were already well served or more likely because they are
less densely populated.
Figure 3c reports a scatter plot of F 15 versus PTcity, analogous to
that of Fig. 1c. The arrows illustrate the changes a selected set of cit -
ies undergo. It is evident how the redistribution of the existing POIs
triggers a leftward and upward movement of the cities, that is, a
trend towards lower values of PTcity (higher average accessibility) and
higher F15 (larger equality). A notable exception is represented by
Atlanta, which warrants a deeper insight. Given the high level of sprawl
in Atlanta, the few compact neighborhoods in the center of Atlanta
worsen their accessibility. Thus, the city sees a small decline in the
proportion of residents within 15-minute areas, despite witnessing
an improvement in its average local accessibility. The distributions of
accessibility scores before and after the relocation of services can be
found in the Supplementary Information.
Our results emphasize the hypothesis that the 15-minute city
paradigm is suitable for relatively compact (that is, high-density) urban
areas. Even if a strategic relocation of services or an increase of their
capillary penetration can notably improve accessibility, the whole
paradigm of the 15-minute city has to be rethought in areas with lower
urban densities, such as suburban or intermediate zones. We shall
return to this point later on.
The quest for inclusive 15-minute cities
So far, we have explored the possibility of better distributing the available opportunities in a city to improve the equality of access to them.
Now, we take a step further and ask ourselves about the optimal number and distribution of POIs to make a 15-minute city for the largest
population fraction.
We can employ our relocation algorithm to simulate any quantity
of POIs in a given city. In particular, we are interested in quantifying the
number of POIs required to become a 15-minute city. With this aim in
mind, we simulated the optimal city structure considering an increasing number of POIs. We ran our algorithm independently for each
POI type (all services are treated equally in our study). This approach
allows us to introduce a parameter for gauging a city’s accessibility:
the number of POIs per 1,000 people.
In Fig. 4, we present the results of our simulations. Figure 4a presents the proportion of the population with a PT below 15 minutes, F15,
which features strong variation across cities. We compute, in particular,
the intercept of the curves with an F 15 of 90%, that is, the number of
POIs per 1,000 residents necessary for 90% of the city’s population
to live within a 15-minute access area. Note that this number is not the
bare minimum required to have widespread 15-minute accessibility,
since the hypothesis of a homogeneous density of POIs per capita is
not always satisfied.
The quantity of POIs per capita required for a city to be a ‘90%
15-minute city’ displays considerable variation among the cities studied. With reference to Fig. 4b, for instance, highly dense and homogeneous cities, like Mumbai and Bogotá, require only 0.45 and 0.56 POIs per
1,000 residents, respectively, to achieve the 15-minute city. This occurs
similarly in many South American cities such as São Paulo, Mexico City
and Fortaleza. Of course, the debate is wide open about the potential
overcrowding of POIs and their quality, but this topic falls beyond the
scope of our current study.
European and Asian cities present a varied landscape. They lie in an
intermediate zone, displaying differing trends based on their urban layout and design. For instance, cities historically designed with a greater
focus on automobile transit, like Rotterdam, or with large suburban
areas, like Tallinn, Edinburgh, Amsterdam or Helsinki, require a higher
number of POIs per capita to become 15-minute cities. This is also the
case in cities in Australia and New Zealand. By contrast, compact cities,
–30 –20 –10 0 10 20 30
Accessibility diﬀerence (min)
0 10 20 30 40 50
0
20
40
60
80
100
Atlanta
Tokyo Bogotá
Hanoi
São Paulo
Dallas
Paris
Beijing Mexico City
Rotterdam
Real city
Optimal city
Impossible area
b
c
a
Atlanta
Rome
F15
PT city  (min)
Fig. 3 | Impact of POIs relocation on accessibility. a,b, The accessibility
difference after applying the algorithm to Rome (a) and Atlanta (b): red areas get
worse because they are over-served or uninhabited. By contrast, blue areas are
under-served and consequently improve their accessibility. c, The change in the
measures of local accessibility depicted in Fig. 1 after applying the algorithm.


## Page 6

such as Turin, Milan and Barcelona, demand fewer POIs per capita due
to their dense and homogeneous urban structure. Another peculiar
case is that of cities with discontinuous urban textures, such as Rome
or Athens, for which historical heritage and geographical constraints
represent an additional challenge towards a compact design.
As already observed, many US cities stand as outliers and represent
unique challenges. T o achieve 15-minute city status, these cities would
require an excessively high number of POIs. Atlanta, for example, would
need more than 15 POIs per 1,000 residents, which translates to one
POI for every 64 residents. Such a requirement appears unsustainable,
once again emphasizing the impact of city density and design on the
feasibility of the 15-minute city concept.
Discussion and conclusions
This study contributes to the ongoing conversation on urban planning
and design by quantifying local accessibility worldwide and offering an
empirical method for simulating scenarios towards proximity-based
cities that optimize equal access to opportunities. The contribution
of this paper is twofold: methodological and conceptual.
On the methodological side, we have introduced a tool to quantify
how close a city is to the 15-minute ideal. We adopted this metric to
assess the status of many cities worldwide. Our open-access platform
(https://whatif.sonycsl.it/15mincity/) allows everyone to explore cities
or portions of them. The second crucial methodological contribu -
tion is the conception and implementation of a heuristic algorithm
to redistribute the POIs in a city based on equal accessibility to the
largest population fraction. Although relocating activities can be a
slow process, POIs related to commercial activities represent a very
fast-paced environment where many activities can be displaced in a
relatively short time, looking for better opportunities. In addition,
many cities are promoting policies of reuse and regeneration with
frequent changes in the intended use of buildings. We tested the algorithm in two conditions: the relocation of existing POIs and the quest
for optimal POIs given the local population densities.
On the conceptual side, this paper provides several essential
observations.
First, we provided a global picture of current local accessibility. We
drew accessibility maps based on the computation of a new observable,
the PT score, which quantifies the time needed from each local area to
reach the essential urban services by walking and cycling. Our results
highlight a profound heterogeneity in accessibility patterns within and
across cities, mirroring different aspects, from geomorphological/
ecological to historical/cultural and management. In the comparison
among cities, marked variations appear, with only a tiny proportion
of the cities very well positioned to become 15-minute cities and an
extensive distribution on more or less large values of the score. Stark
contrasts are also found in different areas of the same city, with the
inequality of accessibility usually following a core-periphery gradient
and a few cities that seem to have more polycentric accessibility to
services than others. The disparity in the local availability of services
is an additional layer of difference between cities, as some, despite an
excellent average local accessibility, are highly heterogeneous.
Second, we asked ourselves about the possibility of improving
present cities, considering the equality of access to urban opportunities. The first question has been whether a better geographical redistribution of the existing POIs would enhance the accessibility patterns
for a larger fraction of the population. We ran this simulation through
our original relocation algorithm for many different cities, and we
concluded that relocating existing POIs (that is, without deploying
new ones) would achieve the objective of substantially improving the
proximity of peripheral and underserved areas while not impoverishing
the central, already well-served, areas. This result advocates for more
decentralization policies of the cities’ activities, favoring populated
peripheral areas.
Finally, we asked whether it is possible to conceive cities that would
be optimal from the perspective of equal access to opportunities. In
this case, we simulate scenarios of the geographical distribution of
POIs by removing the constraints of the present distribution of POIs.
Mumbai
0.45
Bogotá
0.56
T urin
0.73
São P
aulo
0.74
F ortaleza
0.78
Milan
0.82
Addis Ababa
0.90
Copenhagen
0.94
Barcelona
0.97
Rio de Janeiro
1.00
Nairobi
1.00
Medellin
1.03
Seoul1.09
Munich1.10
Mexico City
1.11
Shanghai
1.15 Beijing
1.23 V ienna
1.23
Zurich
1.24
Buenos Aires
1.26
T okyo
1.27
Santiago
1.28
London
1.31
P aris
1.39
Montreal
1.40
Berlin
1.44
Osaka
1.63
Sapporo
1.65
Madrid
1.69
Dublin
1.71
Budapest
1.76
Oslo
1.77
Lisbon
1.82
Edinburgh
2.06
W arsaw
2.30
Hanoi
2.34
Athens
2.40
Rome
2.45
Auckland
2.45
F ukuoka 2.58
Prague 2.61Greater Sydney
2.73
Greater Melbourne
2.80
Helsinki
3.23
T allinn
3.36
Rotterdam
4.87
Milwauk
ee
4.99
Amsterdam
5.36
Dallas
7.30
San Antonio
8.61
Minneapolis
8.91
Detroit (Greater)
11.65
Boston
15.03
Atlanta
15.46
POIs needed
per 1,000 people
0
1
3
10
20
ba
90% population
10
1
10
0
10
–1
POIs per 1,000 people
0
20
40
60
80
100
Nair obi
A ddis Ababa
Helsinki
Bogotá
F ortaleza
Boston
R ome
P aris
Mumbai
F15
Fig. 4 | Optimal number of POIs per 1,000 people. a, Values of F15 as a function
of an increasing number of POIs per 1,000 people distributed across the city by
our algorithm. The intersection with an F15 of 90% defines the number of POIs per
1,000 people needed to become a 15-minute city. b, Radial histogram reporting
the number of POIs per 1,000 people needed to become a 15-minute city. This
number is extremely heterogeneous, resulting from very diverse local and global
population densities.


## Page 7

Instead, we simulated the best positioning of an increasing number of
POIs starting from an empty city (that is, without POIs). This simula -
tion allows us to identify, for each city, the minimum number of POIs
needed for the city to be 15-minute for at least 90% of their residents.
This observable nicely illustrates how hard it is for a city to become
15-minute, and how large the fluctuations are across cities. In some
urban contexts, particularly in US cities, the number of POIs per capita
would be too large to be economically sustainable. A scenario emerges
in which the very notion of the 15-minute city can not be a one-fits-all
solution and is not a viable option in areas with a too-low density and a
pronounced sprawl. On the other side of the spectrum, in many dense
cities, the number of POIs needed is relatively low and can thus be
achieved with minimum effort from policy-makers. Paris, Barcelona,
and Milan represent compelling examples demonstrating the efficacy
of urban planning policies oriented towards local accessibility. On the
other hand, there are major urban centers in the Global South, such
as Nairobi, Mumbai and Addis Ababa, that currently have fewer POIs
compared to the previous examples, but still demonstrate the potential
for effective urban planning focused on local accessibility. Although
our analysis on the current accessibility of African and developing cities
can be biased by a lack of complete and reliable open data (see the Supplementary Section 4 for further discussion on this bias), the analysis
of the optimal distribution reveals the potential of these dense cities
to supply proximity services. These examples are potent arguments
for the feasibility of 15-minute cities in dense urban areas and offer
valuable lessons for other cities aiming to achieve similar outcomes.
As for more sprawling cities, for instance, US cities, the low densities
doom them far from the idea of a proximity-based city.
Since a substantial increase in population density in already inhabited areas is not an option in many cases, a more general theoretical
framework27 is appropriate to include local population densities as
a relevant variable for non-compact urban contexts. In addition, distinguishing essential from non-essential services and their varying
abundance is important to distinguish the feasibility of local proximity
for categories of services. Only some of the POIs have the same degree
of replication. One can easily open a new grocery store virtually eve -
rywhere, but one cannot replicate a landmark monument or major
infrastructure (for example, hospital, opera theater, football stadium)
in every neighborhood. For this reason, it is interesting to promote a
slightly different notion of city in which what is optimized is not only
the transit time but the amount of opportunities, wherever they are,
available to residents.
Before concluding, let us remark that since our analysis is based
on open data, it can be subject to some limitations depending on possible sources of bias. For instance, POIs data coverage can be limited in
some areas or cities, or the walkability of some areas could be different
in some cases 28. Another limitation is that all categories of POIs are
treated the same within and between different cities. Future work must
consider climatic variations and cultural differences by adjusting the
weights of different POI categories according to local preferences and
needs. These minor issues can be progressively solved using more precise and complete data. The interested reader can find a more detailed
discussion about possible critical points in Supplementary Section 4.
In conclusion, our research represents a crucial step forward in
understanding urban accessibility and the viability of proximity-based
cities. Although our findings might provide a new perspective on
traditional planning approaches, they offer practical and actionable
insights for designing sustainable, accessible and liveable urban environments. Our work also highlights that the ideal of a proximity-based
city heralded by the 15-minute city must be balanced by faster and
more reliable public transportation services that allow for eliminating
some of the disparities in peripheries, particularly those due to the heterogeneity of local population densities. Finally, a broader perspective
integrating socio-economic and cultural factors should be included as
a next step to shift focus from only time-based to value-based cities.
As we walk towards imagining future cities, we hope our research
catalyzes deeper exploration and triggers concrete actions in urban
planning and policy.
Methods
The data analysis was mainly performed using Python and the Geo -
Pandas package29, as well as Open Source Routing Machine (OSRM)30
through calls to their API.
Data Acquisition
The data acquisition stage involved collecting four core datasets:
•	 City boundaries. The boundaries of the cities were acquired from
Organisation for Economic Co-operation and Development
(OECD) shapefiles31, focusing on the defined core city. When OECD
data were unavailable, we used the Global Human Settlement
files32, focusing on the city’s core for the analysis.
•	 POIs. Amenities, which we generically refer to as POIs, were
sourced from OpenStreetMap33 and classified according to their
tags. Only POIs representing services for people were retained,
and non-service POIs such as trees and buildings were disregarded.
•	 Population data. Population data were derived from WorldPop34,
providing demographic context for our accessibility measures.
Our study used a 100 m population density grid corrected to match
municipal UN population estimates35.
•	 Times of accessibility. The times of accessibility to POIs from
points in the city were calculated using OSRM30, based on OpenStreetMap data.
Data preparation
The data preparation stage encompassed two main steps:
•	 Hexagonal grid generation. A regular hexagonal grid with a side
length of 200 m was generated across the city. Hexagons without
any nearby POIs were omitted from further analysis.
•	 POI categorization. The retained POIs were categorized into nine
service types: outdoor activities, learning, supplies, eating, moving, cultural activities, physical exercise, services and health care.
This categorization allowed for both general and category-specific
accessibility assessment.
Accessibility calculation
With the prepared data, we proceeded to compute the accessibility.
Our measure of accessibility is similar to what has been proposed in
the literature under the name ‘dual access’15. We compute it as follows:
•	 Hexagon-level accessibility. For each hexagon, k, we identified the
20 nearest POIs in each category using OSRM for both walking and
cycling routes. In the main text, we only show the results for the
simulations for accessibility by walking, and we refer to the online
platform for the simulations about accessibility by bike. The average time 〈t〉c,k required to access the 20 nearest POIs of category c
in the hexagon k, is computed as follows:
⟨t⟩c,k = 1
n
n
∑
i=1
tc,k
i (1)
where n is the number of POIs (in this case, n = 20) and tc,k
i  is the time
required to reach the i -th POI of category c  in the hexagon k .
This procedure yields the accessibility value for that category in that
hexagon, and it is equivalent to calculating the dual access to the 20
closest POIs for each hexagon. We selected a threshold of 20 POIs to
account for choice in accessing services. A small amount of theoretically accessible places can be seen as too restrictive and enhance negative feelings towards proximity-based cities in the general public. In
Supplementary Section 6, we show that changing the number of accessible POIs does not alter the main results of our work, and the PT varies
homogeneously in cities.


## Page 8

•	 City-level accessibility. The accessibility measures for each hexagon k were averaged to generate a single proximity time index PTk
for that hexagon:
PTk = 1
m
m
∑
c=1
⟨t⟩c,k (2)
where m is the number of categories. These indices were then averaged
across the city, weighted by the population pk within each hexagon, to
compute the overall city accessibility PTcity:
PTcity =
∑
K
k=1 PTkpk
∑
K
k=1 pk
(3)
where K is the number of hexagons, PT k is the proximity time index
of the k-th hexagon, and pk is the population of the k-th hexagon. The
corresponding category measures were averaged to derive specific
city scores for individual categories.
•	 15-minute accessibility. We also computed the percentage of
the city’s population within a 15-minute access range, providing
another measure of city-wide accessibility:
F15 =
∑
K
k=1,PTk ≤15 pk
∑
K
k=1 pk
× 100 (4)
Inequality assessment
Lastly, to measure the level of inequality in accessibility across the city,
we calculated the Gini inequality index G:
G = 1 −
2 ∑
Npop
p=1 ∑p′ ≤pPTp′
Npop ∑
Npop
p=1 PTp
(5)
where PTp is the p-th proximity time measure of a single person in the
city when sorted in non-decreasing order and Npop is the total population of a city.
This metric provides a non-trivial measure of urban accessibil -
ity, revealing how unequal local accessibility is in the city. Anyway, a
compact city with a good proximity time will not necessarily have a
low Gini coefficient because the accessibility times can still fluctuate.
POI relocation algorithm
Our algorithm takes the population distribution within the city’s
hexagonal grid as input and optimizes the allocation of POIs inde -
pendently of the category. The optimization is performed separately
for each category. Let us briefly describe the rationale of the algo -
rithm, whose steps are depicted in Fig. 2 . The optimization aims to
keep the number of POIs per capita constant in the city to serve every
area equally, considering its population density. Therefore, each
POI will have to serve on average the same number of people, which
we call capacity CAP and is a global quantity of the considered city
and category:
CAPc =
Npop
Nc
, (6)
where c is a category of services and Nc is the number of POIs of category
c in the city.
The inverse of the capacity is the number of POIs per capita,
reading:
Pc = Nc
Npop
. (7)
Note that we use the number of POIs per thousand people instead
of POIs per capita to improve the measure’s readability and meaning.
A city is initially considered empty and then iteratively filled with
POIs. Each iteration places a POI in the hexagon with the highest population demand (that is, population needing a POI) that can be reached
within a chosen time threshold, 15 minutes in our case. We make the
algorithm slightly random by randomly choosing a neighbor of the
highest demand hexagon to avoid the effect of always choosing the
cells with the locally highest population in need. After placing the POI, a
number of people equal to the POI capacity CAPc will be deducted from
the people in need in the hexagons that can reach the POI in 15 minutes,
in amounts proportional to the population demands of the hexagons.
At the end of this iteration, the total sum of the needing population is
reduced by exactly CAPc. This operation is iterated until all POIs have
been assigned to a hexagon, yielding an equal distribution of services
per capita across the city. The algorithm is the same for all categories,
and it is dependent only on the city’s population distribution. The
number of POIs per capita in each 15-minute neighborhood should then
be (roughly) the same across the city and equal to the average POIs per
capita in the city (Fig. 2). A pseudocode for the algorithm can be found
in Supplementary Section 5.
Reporting summary
Further information on research design is available in the Nature
Portfolio Reporting Summary linked to this article.
Data availability
All data used in the analysis is open source and referenced in the Methods. The data supporting the findings of this study are available from
the corresponding author upon request.
Code availability
The code used in the analysis is described as pseudo-code in the Supplementary Information and can be made available upon reasonable
request.
References
1. Moreno, C., Allam, Z., Chabaud, D., Gall, C. & Pratlong, F.
Introducing the ‘15-minute city’: sustainability, resilience and
place identity in future post-pandemic cities. Smart Cities 4,
93–111 (2021).
2. Allam, Z., Bibri, S. E., Chabaud, D. & Moreno, C. The theoretical,
practical, and technological foundations of the 15-minute city
model: proximity and its environmental, social and economic
benefits for sustainability. Energies 15, 6042 (2022).
3. Basbas, S., Campisi, T., Papas, T., Trouva, M. & Tesoriere, G.
The 15-minute city model: the case of Sicily during and after
COVID-19. Commun. Sci. Lett. Univ. Zilina 23, A83–A92 (2023).
4. Rhoads, D., Solé-Ribalta, A., González, M. C. & Borge-Holthoefer, J.
A sustainable strategy for Open Streets in (post)pandemic cities.
Commun. Phys. 4, 183 (2021).
5. Perry, C. A. in Regional Plan of New York and Its Environs Vol. 7,
21–140 (Regional Plan Association, 1929).
6. Pozoukidou, G. & Angelidou, M. Urban planning in the 15-minute
city: revisited under sustainable and smart city developments
until 2030. Smart Cities 5, 69 (2022).
7. Ribeiro, H. V., Rybski, D. & Kropp, J. P. Effects of changing
population or density on urban carbon dioxide emissions. Nat.
Commun. 10, 3204 (2019).
8. Haaland, C. & van Den Bosch, C. K. Challenges and strategies for
urban green-space planning in cities undergoing densification: a
review. Urban For. Urban Green. 14, 760–771 (2015).
9. Khavarian-Garmsir, A. R., Sharifi, A. & Sadeghi, A. The 15-minute
city: urban planning and design efforts toward creating
sustainable neighborhoods. Cities 132, 104101 (2023).


## Page 9

10. Burton, E. The compact city: just or just compact? A preliminary
analysis. Urban Stud. 37, 1969–2006 (2000).
11. Lima, F. T. & Costa, F. The quest for proximity: a systematic
review of computational approaches towards 15-minute cities.
Architecture 3, 393–409 (2023).
12. Pozoukidou, G. & Chatziyiannaki, Z. 15-minute city: decomposing
the new urban planning eutopia. Sustainability 13, 928 (2021).
13. Levinson, D. & Wu, H. Towards a general theory of access.
J. Transp. Land Use 13, 129–158 (2020).
14. Levinson, D. & King, D. Transport Access Manual: A Guide for
Measuring Connection Between People and Places. (Committee of
the Transport Access Manual, Univ. of Sydney, 2020).
15. Cui, M. & Levinson, D. Primal and dual access. Geogr. Anal. 52,
452–474 (2020).
16. Weiss, D. et al. A global map of travel time to cities to assess
inequalities in accessibility in 2015. Nature 553, 333–336 (2018).
17. Biazzo, I., Monechi, B. & Loreto, V. General scores for accessibility
and inequality measures in urban areas. R. Soc. Open Sci. 6,
190979 (2019).
18. Liu, S. et al. Studying the distribution patterns, dynamics and
influencing factors of city functional components by gradient
analysis. Sci. Rep. 11, 17802 (2021).
19. Kaufmann, T., Radaelli, L., Bettencourt, L. M. A. & Shmueli, E.
Scaling of urban amenities: generative statistics and implications
for urban planning. EPJ Data Sci. 11, 50 (2022).
20. Bittencourt, T. A. & Giannotti, M. Evaluating the accessibility
and availability of public services to reduce inequalities in
everyday mobility. Transp. Res. Part A Policy Pract. 177, 103833
(2023).
21. Yang, J. Visualizing and assessing the 15-minute city facility
configuration of city region. A study on the Beijing-Tianjin-Hebei
urban agglomeration. Adv. Educ. Humanit. Social Sci. Res. 4,
63 (2023).
22. Vale, D. & Lopes, A. S. Accessibility inequality across europe:
a comparison of 15-minute pedestrian accessibility in cities
with 100,000 or more inhabitants. npj Urban Sustain. 3,
55 (2023).
23. Gastner, M. T. & Newman, M. E. J. Optimal design of spatial
distribution networks. Phys. Rev. E 74, 016117 (2006).
24. Xu, Y., Olmos, L. E., Abbar, S. & González, M. C. Deconstructing
laws of accessibility and facility distribution in cities. Sci. Adv. 6,
eabb4112 (2020).
25. Lima, F. T., Brown, N. C. & Duarte, J. P. A grammar-based
optimization approach for designing urban fabrics and locating
amenities for 15-minute cities. Buildings 12, 1157 (2022).
26. Fan, C., Jiang, X., Lee, R. & Mostafavi, A. Equality of access and
resilience in urban population-facility networks. npj Urban
Sustain. 2, 9 (2022).
27. Logan, T. M. et al. The x-minute city: measuring the 10, 15,
20-minute city and an evaluation of its use for sustainable urban
design. Cities 131, 103924 (2022).
28. Rhoads, D., Solé-Ribalta, A. & Borge-Holthoefer, J. The inclusive
15-minute city: walkability analysis with sidewalk networks.
Comput. Environ. Urban Syst. 100, 101936 (2023).
29. Jordahl, K. et al. GeoPandas v0.12.1 (2022).
30. Luxen, D. & Vetter, C. Real-time routing with OpenStreetMap
data. In Proc. 19th ACM SIGSPATIAL International Conference
on Advances in Geographic Information Systems 513–516
(Association for Computing Machinery, 2011).
31. Dijkstra, L., Poelman, H. & Veneri, P. The EU-OECD Definition of a
Functional Urban Area (OECD, 2019).
32. Florczyk, A. J. et al. GHS Urban Centre Database 2015,
multitemporal and multidimensional attributes, R2019A (European
Commission, Joint Research Centre, 2019).
33. OpenStreetMap (accessed May 2023); https://planet.osm.org
34. WorldPop (Univ. of Southampton, accessed January 2023);
https://worldpop.org
35. Bondarenko, M., Kerr, D., Sorichetta, A. & Tatem, A. Census/
projection-disaggregated gridded population datasets for 189
countries in 2020 using Built-Settlement Growth Model (BSGM)
outputs. worldpop https://www.worldpop.org/doi/10.5258/
SOTON/WP00684 (2020).
Acknowledgements
The authors thank B. Monechi and C. Chiappetta for their contributions.
Author contributions
All authors designed the research and analysis. B.C. and M.B.
performed the data analysis. V.L., M.B. and H.P.M.M. wrote the paper.
All authors revised the paper.
Competing interests
The authors declare no competing interests.
Additional information
Supplementary information The online version
contains supplementary material available at
Correspondence and requests for materials should be addressed to
Matteo Bruno.
Peer review information Nature Cities thanks Elsa Arcaute,
Gerhard Schmitt and the other, anonymous, reviewer(s) for their
contribution to the peer review of this work.
Reprints and permissions information is available at
www.nature.com/reprints.
Publisher’s note Springer Nature remains neutral with regard to
jurisdictional claims in published maps and institutional affiliations.
Springer Nature or its licensor (e.g. a society or other partner) holds
exclusive rights to this article under a publishing agreement with
the author(s) or other rightsholder(s); author self-archiving of the
accepted manuscript version of this article is solely governed by the
terms of such publishing agreement and applicable law.
© The Author(s), under exclusive licence to Springer Nature America,
Inc. 2024
