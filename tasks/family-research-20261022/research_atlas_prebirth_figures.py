"""Display descriptive precursor contrasts without significance claims."""
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_atlas import OUT
from research_atlas_figures import finish


def main():
    summary = pd.read_csv(OUT/'prebirth-summary.csv')
    fig,axes = plt.subplots(1,2,figsize=(13,5),layout='constrained')
    fig.suptitle('Before setup birth: candidate differences must recur across conditions',fontsize=17)
    settings = [('family_start','total1','Family starts: fresh classified volume','Case minus control: lots in prior second'),
                ('dipole_birth','displayed_lots','Dipole births: displayed touch depth','Case minus control: displayed lots')]
    for ax,(population,feature,title,ylabel) in zip(axes,settings):
        for quarter,color in zip((1,2,3,4),('#0072B2','#D55E00','#009E73','#CC79A7')):
            g=summary[summary.population.eq(population)&summary.feature.eq(feature)&summary.quarter.eq(quarter)].sort_values('lead_s')
            ax.plot(g.lead_s,g.mean_difference,marker='o',color=color,label=f'Session quarter {quarter}')
        ax.axhline(0,color='#777777',linewidth=.8)
        ax.set_xticks([1,5,20,60]);ax.set_xlabel('Seconds before recorded birth')
        ax.set_ylabel(ylabel);ax.set_title(title,loc='left');ax.legend(fontsize=9)
    fig.supxlabel('October 18 discovery · matched earlier controls may be reused · leads and outcomes overlap · no error bars or significance claim',fontsize=10)
    finish(fig,'prebirth-candidate-contrasts')


if __name__=='__main__':
    main()
