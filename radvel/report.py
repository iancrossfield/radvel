import subprocess
import copy
import numpy as np
import os
import tempfile
import shutil

import radvel

print_basis = 'per tc e w k'
units = {'per': 'days',
         'tp': 'JD',
         'tc': 'JD',
         'e': '',
         'w': 'degrees',
         'k': 'm s$^{-1}$',
         'logk': '$\\ln{(\\rm m\\ s^{-1})}$',
         'secosw': '',
         'sesinw': '',
         'gamma': 'm s$-1$',
         'jitter': 'm s$-1$',
         'logjit': '$\\ln{(\\rm m\\ s^{-1})}$',
         'jit': '$\\rm m\\ s^{-1}$',
         'dvdt': 'm s$^{-1}$ day$^{-1}$',
         'curv': 'm s$^{-1}$ day$^{-2}$'}

latex_compiler = 'pdflatex'

class RadvelReport():
    """Radvel report

    Class to handle the creation of the radvel summary PDF

    Args:
        planet (planet object): planet configuration object loaded in `kepfit.py` using `imp.load_source`
        post (radvel.posterior): radvel.posterior object containing the best-fit parameters in post.params
        chains (DataFrame): output DataFrame from a `radvel.mcmc` run
    """
    
    def __init__(self, planet, post, chains):
        self.planet = planet
        self.post = post
        
        self.starname = planet.starname
        
        printpost = copy.deepcopy(post)
        printpost.params = printpost.params.basis.to_cps(printpost.params)
        printpost.params = printpost.params.basis.from_cps(printpost.params, print_basis)
        self.latex_dict = printpost.params.tex_labels()
        
        printchains = copy.deepcopy(chains)
        for p in post.params.keys():
            if p not in chains.columns:
                chains[p] = post.params[p]
        self.chains = printpost.params.basis.to_cps(chains)
        self.chains = printpost.params.basis.from_cps(chains, print_basis)
        self.quantiles = chains.quantile([0.159, 0.5, 0.841])
        
    def _preamble(self):
        return """
\\documentclass{emulateapj}
\\usepackage{graphicx,textcomp}
\\begin{document}
\\shorttitle{Summary of \\texttt{RADVEL} results for %s}
""" % (self.starname)

    def _postamble(self):
        return """
\\end{document}"""
    

    def texdoc(self):
        """TeX for entire document

        TeX code for the entire output results PDF

        Returns:
            string: TeX code for report
        """

        out = self._preamble() + self.tabletex()
        if os.path.exists(self.starname+"_rv_multipanel.pdf"):
            out += self.figtex(self.starname+"_rv_multipanel.pdf", caption=self._bestfit_caption())
        if os.path.exists(self.starname+"_corner.pdf"):
            out += self.figtex(self.starname+"_corner.pdf", caption="Posterior distributions for all free parameters.")
        if os.path.exists(self.starname+"_corner_derived_pars.pdf"):
            out += self.figtex(self.starname+"_corner_derived_pars.pdf", caption="Posterior distributions for all derived parameters.")

        out += self._postamble()
        
        return out

    def tabletex(self):
        return TexTable(self).tex()

    def figtex(self, infile, caption=""):
        """Generate TeX for figure

        Generate TeX to insert a figure into the report

        Args:
            infile (string): file name of figure
            caption (string): (optional) figure caption

        Returns:
            string: TeX code
        
        """
        fstr = """
\\begin{figure*}[!h]
\\centering
\\includegraphics[width=6.5in]{%s}
\\caption{%s}
\\end{figure*}
""" % (infile, caption)

        return fstr

    def _bestfit_caption(self):
        cap = """
Best-fit %d-planet Keplerian orbital model for %s.
The maximum likelihood model is plotted while the orbital parameters listed in Table \\ref{tab:params}
are the median values of the posterior distributions.
The thin blue line is the best fit %d-planet model. We add in quadrature the RV jitter term(s) listed in Table \\ref{tab:params}
with the measurement uncertainties for all RVs.
{\\bf b)} Residuals to the best fit %d-planet model.
{\\bf c)} RVs phase-folded to the ephemeris of planet %s. The Keplerian orbital models for all other planets (if any) have been subtracted.
The small point colors and symbols are the same as in panel {\\bf a}.
Red circles (if present) are the same velocities binned in 0.08 units of orbital phase.
The phase-folded model for planet %s is shown as the blue line.
""" % (self.post.params.num_planets, self.starname, self.post.params.num_planets, self.post.params.num_planets, chr(int(1)+97), chr(int(1)+97))

        for i in range(1, self.post.params.num_planets):
            cap += "Panel {\\bf %s)} is the same as panel {\\bf %s)} but for planet %s %s.\n" % (chr(int(i)+99), chr(int(i)+98), self.starname, chr(int(i)+98))

        return cap
              
    def compile(self, pdfname, depfiles=[]):
        """Compile radvel report

        Compile the radvel report from a string containing TeX code
        and save the resulting PDF to a file.

        Args:
            pdfname (string): name of the output PDF file
            depfiles (list): list of file names of dependencies needed for LaTex compilation (e.g. figure files)
        """
        texname = os.path.basename(pdfname).split('.')[0] + '.tex'
        
        current = os.getcwd()
        temp = tempfile.mkdtemp()
        for fname in depfiles:
            shutil.copy2(os.path.join(current,fname), os.path.join(temp,fname))
        
        os.chdir(temp)

        f = open(texname, 'w')
        f.write(self.texdoc())
        f.close()

        # LaTex likes to be compiled a few times
        # to get the table widths correct
        if radvel.utils.cmd_exists(latex_compiler):
            for i in range(3):
                proc = subprocess.Popen([latex_compiler, texname], stdout=subprocess.PIPE)
                proc.communicate()

            shutil.copy(pdfname, current)
        else:
            print "WARNING: REPORT: Could not locate %s executable. Failed to generate summary report PDF. \
            Make sure that %s is installed and in your system's PATH." % (latex_compiler, latex_compiler)
            
        shutil.copy(texname, current)
        shutil.rmtree(temp)

        os.chdir(current)

class TexTable(RadvelReport):
    """LaTeX table

    Class to handle generation of the LaTeX tables within the summary PDF.

    Args:
        report (radvel.report.RadvelReport): radvel report object
    """
    
    def __init__(self, report):
        self.report = report
        self.post = report.post
        self.quantiles = report.quantiles
        self.fitting_basis = report.post.params.basis.name
    
    def _header(self):
        fstr = """
\\begin{deluxetable}{lrr}
\\tablecaption{MCMC Posteriors}
\\tablehead{\\colhead{Parameter} & \\colhead{Value} & \\colhead{Units}}
\\startdata
"""
        return fstr

    def _footer(self):
        fstr = """
\\enddata
\\tablenotetext{}{%d links saved}
\\tablenotetext{}{Reference epoch for $\\gamma$,$\\dot{\\gamma}$,$\\ddot{\\gamma}$: %15.1f}
\\label{tab:params}
\\end{deluxetable}
""" % (len(self.report.chains),self.report.post.likelihood.model.time_base)
        return fstr
    
    def _row(self, param, unit):
        med = self.quantiles[param][0.5]
        low = self.quantiles[param][0.5] - self.quantiles[param][0.159]
        high = self.quantiles[param][0.841] - self.quantiles[param][0.5]

        tex = self.report.latex_dict[param]

        low = radvel.utils.round_sig(low)
        high = radvel.utils.round_sig(high)
        med, errlow, errhigh = radvel.utils.sigfig(med, low, high)

        if errlow <= 1e-12 or errhigh <= 1e-12:
            med = "$\\equiv$ %s" % round(self.quantiles[param][0.5],4)
            errfmt = ''
        else:
            if errhigh == errlow: errfmt = '$\pm %s$' % (errhigh)    
            else: errfmt = '$^{+%s}_{-%s}$' % (errhigh,errlow)

        row = "%s & %s %s & %s\\\\\n" % (tex,med,errfmt,unit)

        return row

    
    def _data(self, basis, sidehead=None, hline=False):

        tabledat = ""
        if hline:
            tabledat += "\\hline\n"
        if sidehead is not None:
            tabledat += "\\sidehead{%s}\n" % sidehead

        suffixes = ['_'+j for j in self.report.post.likelihood.suffixes]
            
        for n in range(1,self.report.planet.nplanets+1):
            for p in basis.split():
                
                unit = units.get(p, '')
                if unit == '':
                    for s in suffixes:
                        if s in p:
                            unit = units.get(p.replace(s, ''), '')
                            break
                        
                par = p+str(int(n))
                try:
                    tabledat += self._row(par, unit)
                except KeyError:
                    tabledat += self._row(p, unit)

        return tabledat

    def prior_summary(self):
        """Summary of priors

        Summarize the priors in separate table within the report PDF.

        Returns:
            string: String containing TeX code for the prior summary table
        """
        
        out = """
\\begin{deluxetable}{lrr}
\\tablecaption{Summary of Priors}
\\tablehead{}
\\startdata
"""
        texdict = self.post.likelihood.params.tex_labels()
        
        prior_list = self.post.priors
        for prior in prior_list:
            out += prior.__str__() + "\\\\\\\\\n"

        out += """
\\enddata
\\end{deluxetable}
"""
        return out
    
    def tex(self):
        """TeX code for table

        Returns:
            string: TeX code for the results table in the radvel report.
        """
        # Sort extra params
        ep = []
        order = ['gamma', 'dvdt', 'curv', 'jit']
        for o in order:
            op = []
            for p in self.post.likelihood.extra_params:
                if o in p:
                    op.append(p)
            if len(op) == 0: op = [o]
            [ep.append(i) for i in sorted(op)[::-1]]
        ep = ' '.join(ep)
                        
        outstr = self.comp_table() + \
                 self._header() + \
                 self._data(self.fitting_basis, sidehead='\\bf{Modified MCMC Step Parameters}') + \
                 self._data(print_basis, sidehead='\\bf{Orbital Parameters}', hline=True) + \
                 self._data(ep, sidehead='\\bf{Other Parameters}', hline=True) + \
                 self._footer() + \
                 self.prior_summary()

        # Remove duplicate lines from the
        # step parameters section of the table
        lines = outstr.split('\n')
        trimstr = ""
        for i,line in enumerate(lines):
            if line not in lines[i+1:] or line.startswith('\\') or line == "":
                trimstr += line + "\n"
                 
        return trimstr


    def comp_table(self):
        """Model comparisons

        Compare models with increasing number of planets

        Returns:
            string: String containing TeX code for the model comparison table
        """

        statsdict = radvel.fitting.model_comp(self.post, verbose=False)
        n_test = range(len(statsdict))

        coldefs = 'r'*len(statsdict)
        
        tstr = """
\\begin{deluxetable*}{l%s}
\\tablecaption{Model Comparison}
\\tablehead{\\colhead{Statistic}""" % coldefs
        for n in n_test:
            if n == max(n_test):
                tstr = tstr + " & \\colhead{{\\bf %d planets (adopted)}}" % n
            else:
                tstr = tstr + " & \\colhead{%d planets}" % n
        tstr += "}\n"
            
        tstr += "\\startdata\n\n"

        statkeys = statsdict[0].keys()
        for s in statkeys:
            row = "%s (%s) " % (s, statsdict[0][s][1])
            for n in n_test:
                row += " & %s" % statsdict[n][s][0]

            row += "\\\\\n"
            tstr += row
        tstr += """
\\enddata
\\label{tab:comp}
\\end{deluxetable*}
"""

        return tstr
